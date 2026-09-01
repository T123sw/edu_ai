"""Version- and owner-isolated Q&A orchestration for static course resources."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any
from urllib.parse import quote

import anyio

from app.chat.model_gateway import ChatModelGateway
from app.integrations.openmaic import OpenMaicError
from app.persistence.dependencies import get_postgres_material_repository
from app.schemas.resource_qa import ResourceQaTurnRequest
from app.services.classroom_qa_store import (
    ClassroomQaBusyError,
    ClassroomQaSessionStore,
    resource_session_id,
)
from app.services.classroom_qa_tts import ClassroomQaTtsService
from app.services.resource_qa_prompt import (
    build_resource_qa_context,
    build_resource_qa_messages,
    parse_resource_qa_answer,
)
from core.config import Config
from core.course_storage import CourseStorageManager, storage_manager


MATERIAL_TYPE_BY_RESOURCE_KIND = {"study_guide": "report", "practice": "quiz"}
log = logging.getLogger("resource.qa")


class ResourceQaError(RuntimeError):
    def __init__(self, code: str, public_message: str, *, status_code: int, retryable: bool) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code
        self.retryable = retryable


class ResourceQaService:
    def __init__(
        self,
        *,
        repository: Any | None = None,
        store: ClassroomQaSessionStore | None = None,
        storage: CourseStorageManager | None = None,
        gateway: Any | None = None,
        tts: Any | None = None,
    ) -> None:
        self.repository = repository or get_postgres_material_repository()
        self.storage = storage or storage_manager
        self.store = store or ClassroomQaSessionStore(self.storage)
        self.gateway = gateway or ChatModelGateway(
            api_base=Config.DEEP_MODEL_API_BASE,
            api_key=Config.DEEP_MODEL_API_KEY,
            model_name=Config.LLM_MODEL_DEEP,
        )
        self.tts = tts or ClassroomQaTtsService()

    async def get_session(
        self,
        *,
        course_id: str,
        resource_kind: str,
        resource_id: str,
        resource_version: int,
        owner_user_id: str,
        course_role: str,
    ) -> dict[str, Any]:
        await self._load_resource(
            course_id=course_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
            course_role=course_role,
        )
        internal_id = resource_session_id(
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
        )
        session = self.store.load_or_empty(
            course_id=course_id,
            classroom_id=internal_id,
            owner_user_id=owner_user_id,
        )
        return self._public_session(
            session,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
        )

    async def submit_turn(
        self,
        *,
        course_id: str,
        resource_kind: str,
        resource_id: str,
        resource_version: int,
        owner_user_id: str,
        course_role: str,
        request: ResourceQaTurnRequest,
    ) -> dict[str, Any]:
        if request.resource_version != resource_version:
            raise self._not_found()
        material = await self._load_resource(
            course_id=course_id,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
            course_role=course_role,
        )
        internal_id = resource_session_id(
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
        )
        session = self.store.get_or_create(
            course_id=course_id,
            classroom_id=internal_id,
            owner_user_id=owner_user_id,
        )
        client_turn_id = str(request.client_turn_id)
        existing = self.store.find_turn(session, client_turn_id)
        if existing is not None:
            return self._response_for(session, existing)
        claim_context = {
            "resource_kind": resource_kind,
            "resource_id": resource_id,
            "resource_version": resource_version,
            "anchor": request.anchor.model_dump() if request.anchor else None,
        }
        try:
            self.store.begin_turn(
                session=session,
                client_turn_id=client_turn_id,
                question=request.question,
                checkpoint=claim_context,
            )
        except ClassroomQaBusyError as exc:
            raise ResourceQaError(
                "RESOURCE_QA_BUSY",
                "当前问答仍在处理中，请稍候。",
                status_code=409,
                retryable=True,
            ) from exc

        include_answers = course_role in {"owner", "editor"}
        try:
            context = build_resource_qa_context(
                resource_kind=resource_kind,  # type: ignore[arg-type]
                material=material,
                question=request.question,
                anchor=request.anchor.model_dump() if request.anchor else None,
                include_answers=include_answers,
            )
            messages = build_resource_qa_messages(
                question=request.question,
                context=context,
                recent_turns=list(session.get("turns") or []),
            )
            raw_answer = await anyio.to_thread.run_sync(
                partial(self.gateway.chat, messages, temperature=0.2, max_tokens=800)
            )
            answer_text, transition_text = parse_resource_qa_answer(
                raw_answer,
                resource_title=context.resource_title,
            )
        except Exception as exc:
            self.store.fail_turn(
                session=session,
                client_turn_id=client_turn_id,
                error_code="RESOURCE_QA_ANSWER_FAILED",
                retryable=True,
            )
            raise ResourceQaError(
                "RESOURCE_QA_ANSWER_FAILED",
                "暂时无法生成回答，请稍后重试。",
                status_code=502,
                retryable=True,
            ) from exc

        turn_id = self._turn_id(session["session_id"], client_turn_id)
        try:
            filename, mime_type = await self.tts.synthesize_and_store(
                session_dir=self.store.session_dir(
                    course_id=course_id,
                    classroom_id=internal_id,
                    owner_user_id=owner_user_id,
                ),
                turn_id=turn_id,
                text=f"{answer_text}\n{transition_text}",
            )
            tts_status = "ready"
            audio_url = self._audio_url(
                course_id=course_id,
                resource_kind=resource_kind,
                resource_id=resource_id,
                session_id=session["session_id"],
                filename=filename,
                resource_version=resource_version,
            )
        except (OpenMaicError, OSError, ValueError) as exc:
            log.warning("resource_qa_tts_failed turn_id=%s error=%r", turn_id, exc)
            filename, mime_type, tts_status, audio_url = None, None, "failed", None

        turn = {
            "turn_id": turn_id,
            "client_turn_id": client_turn_id,
            "question": request.question,
            "answer_text": answer_text,
            "transition_text": transition_text,
            "tts_status": tts_status,
            "audio_url": audio_url,
            "audio_filename": filename,
            "audio_mime_type": mime_type,
            "created_at": self._iso_now(),
        }
        completed = self.store.complete_turn(
            session=session,
            client_turn_id=client_turn_id,
            turn=turn,
        )
        return self._response_for(session, completed)

    async def _load_resource(
        self,
        *,
        course_id: str,
        resource_kind: str,
        resource_id: str,
        resource_version: int,
        course_role: str,
    ) -> dict[str, Any]:
        material_type = MATERIAL_TYPE_BY_RESOURCE_KIND.get(resource_kind)
        if not material_type:
            raise self._not_found()
        metadata = await anyio.to_thread.run_sync(
            partial(self.repository.get, course_id, material_type, resource_id)
        )
        if (
            not isinstance(metadata, dict)
            or metadata.get("origin_type") != "standard"
            or metadata.get("standard_kind") != resource_kind
        ):
            raise self._not_found()
        if course_role not in {"owner", "editor"} and metadata.get("approved_version") != resource_version:
            raise self._not_found()
        version = await anyio.to_thread.run_sync(
            partial(self.repository.get_version, course_id, material_type, resource_id, resource_version)
        )
        if (
            not isinstance(version, dict)
            or version.get("origin_type") != "standard"
            or version.get("standard_kind") != resource_kind
        ):
            raise self._not_found()
        return version

    @staticmethod
    def _not_found() -> ResourceQaError:
        return ResourceQaError(
            "RESOURCE_QA_NOT_FOUND",
            "学习资料不存在或当前用户无权读取。",
            status_code=404,
            retryable=False,
        )

    @staticmethod
    def _turn_id(session_id: str, client_turn_id: str) -> str:
        digest = hashlib.sha256(f"{session_id}\0{client_turn_id}".encode("utf-8")).hexdigest()[:16]
        return f"turn_{digest}"

    @staticmethod
    def _audio_url(
        *, course_id: str, resource_kind: str, resource_id: str, session_id: str,
        filename: str, resource_version: int,
    ) -> str:
        course, kind, resource, session, audio = [
            quote(value, safe="")
            for value in (course_id, resource_kind, resource_id, session_id, filename)
        ]
        return (
            f"/api/courses/{course}/resources/{kind}/{resource}/qa/sessions/"
            f"{session}/audio/{audio}?resource_version={resource_version}"
        )

    @classmethod
    def _public_turn(cls, turn: dict[str, Any]) -> dict[str, Any]:
        return {key: turn.get(key) for key in (
            "turn_id", "client_turn_id", "question", "answer_text", "transition_text",
            "tts_status", "audio_url", "created_at",
        )}

    @classmethod
    def _public_session(
        cls, session: dict[str, Any], *, resource_kind: str, resource_id: str, resource_version: int,
    ) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "course_id": session["course_id"],
            "resource_kind": resource_kind,
            "resource_id": resource_id,
            "resource_version": resource_version,
            "owner_user_id": session["owner_user_id"],
            "status": "ready",
            "turns": [cls._public_turn(turn) for turn in session.get("turns") or []],
        }

    @classmethod
    def _response_for(cls, session: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
        return {"session_id": session["session_id"], "turn": cls._public_turn(turn)}

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
