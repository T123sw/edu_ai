"""End-to-end orchestration for one interrupted classroom Q&A turn."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from functools import partial
from typing import Any, Callable
from urllib.parse import quote

import anyio

from app.chat.model_gateway import ChatModelGateway
from app.integrations.openmaic import OpenMaicError
from app.schemas.classroom_qa import ClassroomQaTurnRequest
from app.services.classroom_qa_prompt import (
    ClassroomQaAnswerError,
    StaleClassroomCheckpointError,
    build_classroom_qa_context,
    build_classroom_qa_messages,
    parse_classroom_qa_answer,
)
from app.services.classroom_qa_store import (
    ClassroomQaBusyError,
    ClassroomQaSessionStore,
)
from app.services.classroom_qa_tts import ClassroomQaTtsService
from core.config import Config
from core.course_storage import CourseStorageManager, storage_manager


log = logging.getLogger("classroom.qa")


class ClassroomQaError(RuntimeError):
    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        status_code: int,
        retryable: bool,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code
        self.retryable = retryable


class ClassroomQaService:
    def __init__(
        self,
        *,
        store: ClassroomQaSessionStore | None = None,
        storage: CourseStorageManager | None = None,
        material_loader: Callable[..., Any] | None = None,
        gateway: Any | None = None,
        tts: ClassroomQaTtsService | Any | None = None,
        metrics_sink: Callable[[dict[str, Any]], None] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.storage = storage or storage_manager
        self.store = store or ClassroomQaSessionStore(self.storage)
        self.material_loader = material_loader or self._load_visible_material
        self.gateway = gateway or ChatModelGateway(
            api_base=Config.DEEP_MODEL_API_BASE,
            api_key=Config.DEEP_MODEL_API_KEY,
            model_name=Config.LLM_MODEL_DEEP,
        )
        self.tts = tts or ClassroomQaTtsService()
        self.metrics_sink = metrics_sink or self._log_metrics
        self.clock = clock

    async def get_session(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        material = await self._run_sync(
            self.material_loader,
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        if not isinstance(material, dict):
            raise ClassroomQaError(
                "CLASSROOM_NOT_FOUND",
                "课堂不存在或当前用户无权读取。",
                status_code=404,
                retryable=False,
            )
        session = self.store.load_or_empty(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        return self._public_session(session)

    async def submit_turn(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
        request: ClassroomQaTurnRequest,
    ) -> dict[str, Any]:
        started = self.clock()
        client_turn_id = str(request.client_turn_id)
        checkpoint = request.checkpoint.model_dump()
        context_started = self.clock()
        material = await self._run_sync(
            self.material_loader,
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        if not isinstance(material, dict):
            raise ClassroomQaError(
                "CLASSROOM_NOT_FOUND",
                "课堂不存在或当前用户无权读取。",
                status_code=404,
                retryable=False,
            )

        session = self.store.get_or_create(
            course_id=course_id,
            classroom_id=classroom_id,
            owner_user_id=owner_user_id,
        )
        existing = self.store.find_turn(session, client_turn_id)
        if existing is not None:
            self._emit_metrics(
                started=started,
                course_id=course_id,
                classroom_id=classroom_id,
                session=session,
                client_turn_id=client_turn_id,
                checkpoint=checkpoint,
                result="idempotent",
                code="OK",
            )
            return self._response_for(session, existing)

        try:
            self.store.begin_turn(
                session=session,
                client_turn_id=client_turn_id,
                question=request.question,
                checkpoint=checkpoint,
            )
        except ClassroomQaBusyError as exc:
            raise ClassroomQaError(
                "CLASSROOM_QA_BUSY",
                "当前问答仍在处理中，请稍候。",
                status_code=409,
                retryable=True,
            ) from exc

        try:
            context = build_classroom_qa_context(
                material=material,
                checkpoint=checkpoint,
                recent_turns=list(session.get("turns") or []),
            )
        except StaleClassroomCheckpointError as exc:
            self.store.fail_turn(
                session=session,
                client_turn_id=client_turn_id,
                error_code="STALE_CLASSROOM_CHECKPOINT",
                retryable=False,
            )
            raise ClassroomQaError(
                "STALE_CLASSROOM_CHECKPOINT",
                "课堂位置已经变化，请重新提问。",
                status_code=409,
                retryable=False,
            ) from exc
        context_ms = self._elapsed_ms(context_started)

        llm_started = self.clock()
        try:
            messages = build_classroom_qa_messages(
                question=request.question,
                context=context,
            )
            raw_answer = await anyio.to_thread.run_sync(
                partial(
                    self.gateway.chat,
                    messages,
                    temperature=0.2,
                    max_tokens=800,
                )
            )
            answer_text, transition_text = parse_classroom_qa_answer(
                raw_answer,
                scene_title=context.scene_title,
            )
        except (Exception, ClassroomQaAnswerError) as exc:
            self.store.fail_turn(
                session=session,
                client_turn_id=client_turn_id,
                error_code="CLASSROOM_QA_ANSWER_FAILED",
                retryable=True,
            )
            self._emit_metrics(
                started=started,
                course_id=course_id,
                classroom_id=classroom_id,
                session=session,
                client_turn_id=client_turn_id,
                checkpoint=checkpoint,
                context_ms=context_ms,
                llm_ms=self._elapsed_ms(llm_started),
                result="failed",
                code="CLASSROOM_QA_ANSWER_FAILED",
            )
            raise ClassroomQaError(
                "CLASSROOM_QA_ANSWER_FAILED",
                "暂时无法生成回答，请稍后重试。",
                status_code=502,
                retryable=True,
            ) from exc
        llm_ms = self._elapsed_ms(llm_started)

        turn_id = self._turn_id(session["session_id"], client_turn_id)
        tts_started = self.clock()
        audio_filename: str | None = None
        audio_mime_type: str | None = None
        try:
            audio_filename, audio_mime_type = await self.tts.synthesize_and_store(
                session_dir=self.store.session_dir(
                    course_id=course_id,
                    classroom_id=classroom_id,
                    owner_user_id=owner_user_id,
                ),
                turn_id=turn_id,
                text=f"{answer_text}\n{transition_text}",
            )
            tts_status = "ready"
            audio_url = self._audio_url(
                course_id=course_id,
                classroom_id=classroom_id,
                session_id=session["session_id"],
                filename=audio_filename,
            )
        except (OpenMaicError, OSError, ValueError) as exc:
            log.warning(
                "classroom_qa_tts_failed provider=%s turn_id=%s error_type=%s",
                Config.OPENMAIC_LIVE_TTS_PROVIDER,
                turn_id,
                type(exc).__name__,
            )
            tts_status = "failed"
            audio_url = None
        tts_ms = self._elapsed_ms(tts_started)

        turn = {
            "turn_id": turn_id,
            "client_turn_id": client_turn_id,
            "question": request.question,
            "answer_text": answer_text,
            "transition_text": transition_text,
            "tts_status": tts_status,
            "audio_url": audio_url,
            "audio_filename": audio_filename if tts_status == "ready" else None,
            "audio_mime_type": audio_mime_type if tts_status == "ready" else None,
            "created_at": self._iso_now(),
        }
        completed = self.store.complete_turn(
            session=session,
            client_turn_id=client_turn_id,
            turn=turn,
        )
        self._emit_metrics(
            started=started,
            course_id=course_id,
            classroom_id=classroom_id,
            session=session,
            client_turn_id=client_turn_id,
            checkpoint=checkpoint,
            context_ms=context_ms,
            llm_ms=llm_ms,
            tts_ms=tts_ms,
            result="completed" if tts_status == "ready" else "degraded",
            code="OK",
        )
        return self._response_for(session, completed)

    def _load_visible_material(
        self,
        *,
        course_id: str,
        classroom_id: str,
        owner_user_id: str,
    ) -> dict[str, Any] | None:
        return self.storage.get_generated_material(
            course_id,
            "classroom",
            classroom_id,
            owner_user_id=owner_user_id,
        )

    @staticmethod
    async def _run_sync(function: Callable[..., Any], **kwargs: Any) -> Any:
        return await anyio.to_thread.run_sync(partial(function, **kwargs))

    @staticmethod
    def _turn_id(session_id: str, client_turn_id: str) -> str:
        digest = hashlib.sha256(
            f"{session_id}\0{client_turn_id}".encode("utf-8")
        ).hexdigest()[:16]
        return f"turn_{digest}"

    @staticmethod
    def _audio_url(
        *,
        course_id: str,
        classroom_id: str,
        session_id: str,
        filename: str,
    ) -> str:
        values = [course_id, classroom_id, session_id, filename]
        course, classroom, session, audio = [quote(value, safe="") for value in values]
        return (
            f"/api/courses/{course}/classrooms/{classroom}/qa/"
            f"sessions/{session}/audio/{audio}"
        )

    @classmethod
    def _public_turn(cls, turn: dict[str, Any]) -> dict[str, Any]:
        return {
            key: turn.get(key)
            for key in (
                "turn_id",
                "client_turn_id",
                "question",
                "answer_text",
                "transition_text",
                "tts_status",
                "audio_url",
                "created_at",
            )
        }

    @classmethod
    def _public_session(cls, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "course_id": session["course_id"],
            "classroom_id": session["classroom_id"],
            "owner_user_id": session["owner_user_id"],
            "status": "ready",
            "turns": [cls._public_turn(turn) for turn in session.get("turns") or []],
        }

    @classmethod
    def _response_for(
        cls,
        session: dict[str, Any],
        turn: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "turn": cls._public_turn(turn),
        }

    def _emit_metrics(
        self,
        *,
        started: float,
        course_id: str,
        classroom_id: str,
        session: dict[str, Any],
        client_turn_id: str,
        checkpoint: dict[str, Any],
        context_ms: float = 0.0,
        llm_ms: float = 0.0,
        tts_ms: float = 0.0,
        result: str,
        code: str,
    ) -> None:
        self.metrics_sink(
            {
                "course_id": course_id,
                "classroom_id": classroom_id,
                "session_id": session.get("session_id"),
                "client_turn_id": client_turn_id,
                "checkpoint_scene_id": checkpoint.get("scene_id"),
                "checkpoint_action_id": checkpoint.get("action_id"),
                "context_ms": round(context_ms, 2),
                "llm_ms": round(llm_ms, 2),
                "tts_ms": round(tts_ms, 2),
                "total_ms": round(self._elapsed_ms(started), 2),
                "result": result,
                "code": code,
            }
        )

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self.clock() - started) * 1000)

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _log_metrics(metrics: dict[str, Any]) -> None:
        log.info("classroom_qa_turn metrics=%s", metrics)
