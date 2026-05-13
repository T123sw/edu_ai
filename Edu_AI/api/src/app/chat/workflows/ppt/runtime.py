from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import json
import re
import time
from typing import Any

import httpx

from app.chat.debug_logging import append_debug_log
from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.ppt_outline import PptOutline
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.ppt_context_organizer import PptContextOrganizer

from .content_gate import PptContentGate
from .content_markdown_generator import PptContentMarkdownGenerator
from .content_validator import PptContentValidator
from .html2ppt_client import Html2PptClient
from .outline_builder import PptOutlineBuilder
from .post_outline_executor import PptPostOutlineExecutor
from .readiness_judge import PptReadinessJudge

_AFFIRMATIVE_TOKENS = {
    "可以",
    "开始",
    "继续",
    "确认",
    "确认并继续",
    "确认并生成",
    "开始生成",
    "开始生成ppt",
    "开始生成课件",
    "按这个大纲生成",
    "就按这个生成",
    "yes",
    "ok",
}
_SUPPORTED_THEME_IDS = {"heu_academic_elegant", "heu_academic_basic"}
_DEFAULT_THEME_ID = "heu_academic_elegant"
_DEFAULT_PHASE_POLL_TIMEOUT_SECONDS = {
    "accepted": 1800.0,
    "queued": 1800.0,
    "preprocessing": 1800.0,
    "generating_slides": 1800.0,
    "exporting_pptx": 1800.0,
    "polling_ppt_job": 1800.0,
}


@dataclass
class _ResumePreparation:
    topic: str = ""
    audience: str = ""
    objective: str = ""
    key_points: list[str] | None = None
    source_basis: list[str] | None = None
    source_excerpts: list[str] | None = None
    theme_id: str = ""
    slide_count: int | None = None

    def model_dump(self, exclude_none: bool = True) -> dict[str, Any]:
        payload = {
            "topic": self.topic,
            "audience": self.audience,
            "objective": self.objective,
            "key_points": list(self.key_points or []),
            "source_basis": list(self.source_basis or []),
            "source_excerpts": list(self.source_excerpts or []),
            "theme": self.theme_id,
            "page_count": self.slide_count,
        }
        if not exclude_none:
            return payload
        return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower().strip("。！？,.，；;:")


def _is_affirmative_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if normalized in _AFFIRMATIVE_TOKENS:
        return True
    if "大纲" in normalized and any(token in normalized for token in ("继续", "开始", "确认", "生成")):
        return True
    if any(token in normalized for token in ("生成ppt", "开始生成ppt", "开始生成课件", "导出ppt", "导出课件")):
        return True
    return False


def _normalize_job_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "succeeded":
        return "completed"
    if normalized == "failed":
        return "failed"
    return "running"


def _extract_artifact(workflow_state: Any, artifact_type: str) -> dict[str, Any] | None:
    for artifact in list(getattr(workflow_state, "artifacts", []) or []):
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("artifact_type") or "").strip() == artifact_type:
            return artifact
    return None


def _normalize_theme_id(value: str) -> str:
    text = str(value or "").strip()
    if text in _SUPPORTED_THEME_IDS:
        return text
    return _DEFAULT_THEME_ID


def _normalize_outline_theme(outline: PptOutline) -> PptOutline:
    return outline.model_copy(update={"theme_id": _normalize_theme_id(outline.theme_id)})


def _build_outline_artifact(*, conversation_id: str, outline: PptOutline) -> dict[str, Any]:
    deck_title = str(outline.deck_title or "PPT 大纲").strip() or "PPT 大纲"
    return {
        "artifact_id": f"{conversation_id or 'ppt'}:outline",
        "artifact_type": "ppt_outline",
        "title": f"{deck_title}-大纲",
        "content": outline.model_dump(exclude_none=True),
        "generation_state": {
            "status": "awaiting_confirm",
            "phase": "awaiting_outline_confirmation",
        },
    }


def _build_markdown_artifact(*, conversation_id: str, outline: PptOutline, content_markdown: str) -> dict[str, Any]:
    deck_title = str(outline.deck_title or "PPT").strip() or "PPT"
    return {
        "artifact_id": f"{conversation_id or 'ppt'}:content_markdown",
        "artifact_type": "ppt_content_markdown",
        "title": f"{deck_title}-content.md",
        "content": content_markdown,
        "generation_state": {
            "status": "completed",
            "phase": "assembling_content_markdown",
        },
    }


def _build_deck_artifact(
    *,
    conversation_id: str,
    outline: PptOutline,
    job_id: str,
    job_status_payload: dict[str, Any],
    results_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = _normalize_job_status(job_status_payload.get("status"))
    try:
        resolved_slide_count = int((results_payload or {}).get("slide_count") or 0) if results_payload else 0
    except (TypeError, ValueError):
        resolved_slide_count = 0
    generation_state = {
        "status": normalized_status,
        "phase": str(job_status_payload.get("phase") or ("completed" if normalized_status == "completed" else "polling_ppt_job")),
        "progress": int(job_status_payload.get("progress") or (100 if normalized_status == "completed" else 0)),
        "message": str(job_status_payload.get("message") or ("PPT 已生成完成" if normalized_status == "completed" else "正在生成 PPT")),
    }
    content: dict[str, Any] = {
        "job_id": job_id,
        "theme_id": outline.theme_id,
        "slide_count": resolved_slide_count or len(list(outline.slides or [])),
    }
    if results_payload:
        content["revision_id"] = results_payload.get("latest_revision_id")
        content.update(dict(results_payload.get("results") or {}))
    elif job_status_payload.get("latest_revision_id"):
        content["revision_id"] = job_status_payload.get("latest_revision_id")

    deck_title = str(outline.deck_title or "PPT").strip() or "PPT"
    return {
        "artifact_id": f"{conversation_id or 'ppt'}:deck:{job_id}",
        "artifact_type": "ppt_deck",
        "title": f"{deck_title}.pptx",
        "content": content,
        "generation_state": generation_state,
    }


def _build_metadata(*, request, content_markdown: str, theme_id: str) -> dict[str, str]:
    conversation_id = str(getattr(request, "conversation_id", "") or "")
    user_id = str(getattr(request, "owner", "") or "anonymous")
    digest = sha1(f"{conversation_id}:{theme_id}:{content_markdown}".encode("utf-8")).hexdigest()[:16]
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "request_id": f"ppt-{conversation_id or digest}-{digest[:8]}",
        "timestamp": timestamp,
        "idempotency_key": f"ppt-{digest}",
        "user_id": user_id,
    }


def _build_filled_slots(*, preparation, followup_rounds: int) -> dict[str, str]:
    filled_slots: dict[str, str] = {
        "__ppt_followup_rounds": str(max(int(followup_rounds or 0), 0)),
    }
    if str(getattr(preparation, "topic", "") or "").strip():
        filled_slots["deck_topic"] = str(getattr(preparation, "topic", "") or "").strip()
    if str(getattr(preparation, "audience", "") or "").strip():
        filled_slots["audience"] = str(getattr(preparation, "audience", "") or "").strip()
    if str(getattr(preparation, "objective", "") or "").strip():
        filled_slots["objective"] = str(getattr(preparation, "objective", "") or "").strip()
    key_points = [str(item).strip() for item in list(getattr(preparation, "key_points", []) or []) if str(item).strip()]
    if key_points:
        filled_slots["key_points"] = " | ".join(key_points)
    if str(getattr(preparation, "theme_id", "") or "").strip():
        filled_slots["theme_id"] = str(getattr(preparation, "theme_id", "") or "").strip()
    if getattr(preparation, "slide_count", None):
        filled_slots["slide_count"] = str(getattr(preparation, "slide_count"))
    source_basis = [str(item).strip() for item in list(getattr(preparation, "source_basis", []) or []) if str(item).strip()]
    if source_basis:
        filled_slots["__ppt_source_basis"] = " | ".join(source_basis)
    source_excerpts = [str(item).strip() for item in list(getattr(preparation, "source_excerpts", []) or []) if str(item).strip()]
    if source_excerpts:
        filled_slots["__ppt_source_excerpts_json"] = json.dumps(source_excerpts, ensure_ascii=False)
    return filled_slots


def _build_html2ppt_unreachable_message(exc: Exception) -> str:
    text = str(exc or "").strip()
    if "10061" in text or "actively refused" in text.lower():
        return "PPT 引擎当前未启动或未监听 `127.0.0.1:46080`。请先启动 html2ppt 服务，然后重新确认大纲。"
    return "PPT 引擎当前不可用，暂时无法继续生成。请先检查 html2ppt 服务是否已启动，然后重试。"


class PptWorkflowRuntime:
    def __init__(
        self,
        *,
        generation_context_builder: GenerationContextBuilder | None = None,
        ppt_context_organizer: PptContextOrganizer | None = None,
        readiness_judge: PptReadinessJudge | None = None,
        outline_builder: PptOutlineBuilder | None = None,
        content_markdown_generator: PptContentMarkdownGenerator | None = None,
        content_gate: PptContentGate | None = None,
        content_validator: PptContentValidator | None = None,
        html2ppt_client: Html2PptClient | None = None,
        html2ppt_client_factory=None,
        post_outline_executor: PptPostOutlineExecutor | None = None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 600,
        max_poll_seconds: float = 1800.0,
        phase_poll_timeout_seconds: dict[str, float] | None = None,
    ) -> None:
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.ppt_context_organizer = ppt_context_organizer or PptContextOrganizer()
        self.readiness_judge = readiness_judge or PptReadinessJudge()
        self.outline_builder = outline_builder or PptOutlineBuilder()
        self.content_markdown_generator = content_markdown_generator or PptContentMarkdownGenerator()
        self.content_validator = content_validator or PptContentValidator()
        self.content_gate = content_gate or PptContentGate(content_validator=self.content_validator)
        self._html2ppt_client = html2ppt_client
        self._html2ppt_client_factory = html2ppt_client_factory
        self.poll_interval_seconds = max(float(poll_interval_seconds or 0), 0.0)
        self.max_poll_attempts = max(int(max_poll_attempts or 1), 1)
        self.max_poll_seconds = max(float(max_poll_seconds or 0), 0.0)
        self.phase_poll_timeout_seconds = {
            str(key or "").strip().lower(): max(float(value or 0), 0.0)
            for key, value in dict(phase_poll_timeout_seconds or {}).items()
            if str(key or "").strip()
        }
        self.post_outline_executor = post_outline_executor or PptPostOutlineExecutor(
            content_markdown_generator=self.content_markdown_generator,
            content_gate=self.content_gate,
            content_validator=self.content_validator,
            html2ppt_client=self._html2ppt_client,
            html2ppt_client_factory=self._html2ppt_client_factory,
            poll_interval_seconds=self.poll_interval_seconds,
            max_poll_attempts=self.max_poll_attempts,
            max_poll_seconds=self.max_poll_seconds,
            phase_poll_timeout_seconds=self.phase_poll_timeout_seconds,
        )

    @property
    def html2ppt_client(self) -> Html2PptClient:
        if self._html2ppt_client is None and self._html2ppt_client_factory is not None:
            self._html2ppt_client = self._html2ppt_client_factory()
        if self._html2ppt_client is None:
            raise RuntimeError("html2ppt client is not configured")
        return self._html2ppt_client

    def _build_generation_context(self, *, request, snapshot) -> GenerationContext:
        if snapshot is None:
            return GenerationContext(
                conversation_id=str(getattr(request, "conversation_id", "") or ""),
                resource_type="ppt",
            )
        return self.generation_context_builder.build_for_resource(
            request=request,
            snapshot=snapshot,
            resource_type="ppt",
        )

    @staticmethod
    def _preview_text(value: object, limit: int = 280) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...(+{len(text) - limit} chars)"

    def _summarize_outline(self, outline: PptOutline) -> dict[str, Any]:
        return {
            "deck_title": outline.deck_title,
            "theme_id": outline.theme_id,
            "slide_count": len(list(outline.slides or [])),
            "slides": [
                {
                    "slide_index": slide.slide_index,
                    "role": slide.role,
                    "title": slide.title,
                    "goal_preview": self._preview_text(slide.goal),
                    "key_point_count": len(list(slide.key_points or [])),
                }
                for slide in list(outline.slides or [])
            ],
        }

    def _response(
        self,
        *,
        request,
        message: str,
        workflow: dict[str, Any],
        artifacts: list[dict[str, Any]],
        trace: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "message": {"role": "assistant", "content": message},
            "conversation": {"conversation_id": request.conversation_id or ""},
            "action": {"name": "generate.ppt"},
            "artifacts": artifacts,
            "workflow": workflow,
            "sources": [],
            "trace": trace,
        }

    @staticmethod
    def _normalize_phase_name(value: object) -> str:
        return str(value or "").strip().lower()

    def _phase_timeout_seconds(self, phase: str) -> float:
        normalized_phase = self._normalize_phase_name(phase) or "polling_ppt_job"
        if normalized_phase in self.phase_poll_timeout_seconds:
            return self.phase_poll_timeout_seconds[normalized_phase]
        return float(
            _DEFAULT_PHASE_POLL_TIMEOUT_SECONDS.get(
                normalized_phase,
                self.max_poll_seconds or _DEFAULT_PHASE_POLL_TIMEOUT_SECONDS["polling_ppt_job"],
            )
        )

    def _wait_for_job_terminal_state(self, *, request, job_id: str, initial_status: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
        status_response = dict(initial_status or {})
        if str(status_response.get("job_id") or "").strip() != job_id:
            status_response = {}
        results_response = None
        started_at = time.monotonic()
        phase_started_at = started_at
        current_phase = self._normalize_phase_name(status_response.get("phase")) or "polling_ppt_job"

        for attempt in range(1, self.max_poll_attempts + 1):
            status_response = self.html2ppt_client.get_job_status(job_id)
            polled_at = time.monotonic()
            polled_phase = self._normalize_phase_name(status_response.get("phase")) or "polling_ppt_job"
            if polled_phase != current_phase:
                current_phase = polled_phase
                phase_started_at = polled_at
            append_debug_log(
                "ppt_workflow",
                event="html2ppt_status_polled",
                echo=True,
                conversation_id=str(getattr(request, "conversation_id", "") or ""),
                job_id=job_id,
                attempt=attempt,
                status_response=status_response,
            )
            normalized_status = str(status_response.get("status") or "").strip().lower()
            if normalized_status == "succeeded":
                results_response = self.html2ppt_client.get_job_results(job_id)
                append_debug_log(
                    "ppt_workflow",
                    event="html2ppt_results_loaded",
                    echo=True,
                    conversation_id=str(getattr(request, "conversation_id", "") or ""),
                    job_id=job_id,
                    attempt=attempt,
                    results_response=results_response,
                )
                return status_response, results_response
            if normalized_status == "failed":
                return status_response, None
            total_elapsed = polled_at - started_at
            phase_elapsed = polled_at - phase_started_at
            phase_timeout_seconds = self._phase_timeout_seconds(current_phase)
            overall_timed_out = bool(self.max_poll_seconds) and total_elapsed >= self.max_poll_seconds
            phase_timed_out = bool(phase_timeout_seconds) and phase_elapsed >= phase_timeout_seconds
            if overall_timed_out or phase_timed_out:
                timeout_status = dict(status_response or {})
                timeout_status.setdefault("job_id", job_id)
                timeout_status["status"] = timeout_status.get("status") or "failed"
                timeout_status["phase"] = timeout_status.get("phase") or current_phase or "polling_ppt_job"
                timeout_status["progress"] = int(timeout_status.get("progress") or 0)
                timeout_status["message"] = "PPT generation timed out before completion."
                append_debug_log(
                    "ppt_workflow",
                    event="html2ppt_poll_timed_out",
                    echo=True,
                    conversation_id=str(getattr(request, "conversation_id", "") or ""),
                    job_id=job_id,
                    max_poll_attempts=self.max_poll_attempts,
                    max_poll_seconds=self.max_poll_seconds,
                    phase=current_phase,
                    phase_timeout_seconds=phase_timeout_seconds,
                    total_elapsed_seconds=round(total_elapsed, 3),
                    phase_elapsed_seconds=round(phase_elapsed, 3),
                )
                return timeout_status, None
            if attempt < self.max_poll_attempts and self.poll_interval_seconds > 0:
                time.sleep(self.poll_interval_seconds)

        timeout_status = dict(status_response or {})
        timeout_status.setdefault("job_id", job_id)
        timeout_status["status"] = timeout_status.get("status") or "failed"
        timeout_status["phase"] = timeout_status.get("phase") or "polling_ppt_job"
        timeout_status["progress"] = int(timeout_status.get("progress") or 0)
        timeout_status["message"] = "PPT generation timed out before completion."
        append_debug_log(
            "ppt_workflow",
            event="html2ppt_poll_timed_out",
            echo=True,
            conversation_id=str(getattr(request, "conversation_id", "") or ""),
            job_id=job_id,
            max_poll_attempts=self.max_poll_attempts,
            max_poll_seconds=self.max_poll_seconds,
            phase=current_phase,
        )
        return timeout_status, None

    def _submit_outline(self, *, request, outline: PptOutline, preparation, followup_rounds: int) -> dict[str, Any]:
        outline = _normalize_outline_theme(outline)
        execution = self.post_outline_executor.execute(
            outline=outline,
            request=request,
            metadata={
                "artifact_scope_id": request.conversation_id or "",
                "preparation": preparation,
                "trace_path": "workflow",
                "trace": {
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "ppt_preparation_result": preparation.model_dump(exclude_none=True),
                    "ppt_outline_summary": self._summarize_outline(outline),
                },
            },
        )
        return self._response(
            request=request,
            message=str(execution.get("message") or "PPT 已提交生成"),
            workflow={
                "type": "ppt",
                "status": str(execution.get("status") or "failed"),
                "phase": str(execution.get("phase") or "submitting_ppt_job"),
                "filled_slots": _build_filled_slots(preparation=preparation, followup_rounds=followup_rounds),
            },
            artifacts=list(execution.get("artifacts") or []),
            trace=dict(execution.get("trace") or {}),
        )

    def _poll_existing_job(self, *, request, workflow_state) -> dict[str, Any] | None:
        outline_artifact = _extract_artifact(workflow_state, "ppt_outline")
        deck_artifact = _extract_artifact(workflow_state, "ppt_deck")
        if not outline_artifact or not deck_artifact:
            return None
        job_id = str(((deck_artifact.get("content") or {}).get("job_id")) or "").strip()
        if not job_id:
            return None

        try:
            status_response = self.html2ppt_client.get_job_status(job_id)
            append_debug_log(
                "ppt_workflow",
                event="html2ppt_existing_job_polled",
                echo=True,
                conversation_id=str(getattr(request, "conversation_id", "") or ""),
                job_id=job_id,
                status_response=status_response,
            )
            results_response = None
            if str(status_response.get("status") or "").strip().lower() == "succeeded":
                results_response = self.html2ppt_client.get_job_results(job_id)
                append_debug_log(
                    "ppt_workflow",
                    event="html2ppt_existing_job_results_loaded",
                    echo=True,
                    conversation_id=str(getattr(request, "conversation_id", "") or ""),
                    job_id=job_id,
                    results_response=results_response,
                )
        except httpx.RequestError as exc:
            append_debug_log(
                "ppt_workflow",
                event="html2ppt_existing_job_poll_failed",
                echo=True,
                conversation_id=str(getattr(request, "conversation_id", "") or ""),
                job_id=job_id,
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            outline = PptOutline.model_validate(outline_artifact.get("content") or {})
            markdown_artifact = _extract_artifact(workflow_state, "ppt_content_markdown")
            failed_deck_artifact = _build_deck_artifact(
                conversation_id=request.conversation_id or "",
                outline=outline,
                job_id=job_id,
                job_status_payload={
                    "status": "failed",
                    "phase": "polling_ppt_job",
                    "progress": 0,
                    "message": _build_html2ppt_unreachable_message(exc),
                },
                results_payload=None,
            )
            artifacts = [outline_artifact]
            if markdown_artifact:
                artifacts.append(markdown_artifact)
            artifacts.append(failed_deck_artifact)
            return self._response(
                request=request,
                message=_build_html2ppt_unreachable_message(exc),
                workflow={
                    "type": "ppt",
                    "status": "failed",
                    "phase": "polling_ppt_job",
                    "filled_slots": dict(getattr(workflow_state, "filled_slots", {}) or {}),
                },
                artifacts=artifacts,
                trace={
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "html2ppt_error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc),
                    },
                },
            )
        outline = _normalize_outline_theme(PptOutline.model_validate(outline_artifact.get("content") or {}))
        next_deck_artifact = _build_deck_artifact(
            conversation_id=request.conversation_id or "",
            outline=outline,
            job_id=job_id,
            job_status_payload=status_response,
            results_payload=results_response,
        )
        message = (
            "PPT 已生成完成，请在右侧查看和下载。"
            if next_deck_artifact["generation_state"]["status"] == "completed"
            else str(next_deck_artifact["generation_state"]["message"] or "PPT 正在生成")
        )
        markdown_artifact = _extract_artifact(workflow_state, "ppt_content_markdown")
        artifacts = [outline_artifact]
        if markdown_artifact:
            artifacts.append(markdown_artifact)
        artifacts.append(next_deck_artifact)
        return self._response(
            request=request,
            message=message,
            workflow={
                "type": "ppt",
                "status": next_deck_artifact["generation_state"]["status"],
                "phase": next_deck_artifact["generation_state"]["phase"],
                "filled_slots": dict(getattr(workflow_state, "filled_slots", {}) or {}),
            },
            artifacts=artifacts,
            trace={
                "path": "workflow",
                "workflow_name": "ppt",
                "html2ppt_job": {
                    "status_response": status_response,
                    "results_response": results_response,
                },
            },
        )

    @staticmethod
    def _load_resume_source_excerpts(*, filled_slots: dict[str, Any]) -> list[str]:
        raw_json = str(filled_slots.get("__ppt_source_excerpts_json") or "").strip()
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in str(filled_slots.get("__ppt_source_excerpts") or "").split("|") if item.strip()]

    def _build_resume_preparation(self, *, workflow_state) -> _ResumePreparation:
        filled_slots = dict(getattr(workflow_state, "filled_slots", {}) or {})
        slide_count = int(str(filled_slots.get("slide_count") or "0") or 0) or None
        return _ResumePreparation(
            topic=str(filled_slots.get("deck_topic") or ""),
            audience=str(filled_slots.get("audience") or ""),
            objective=str(filled_slots.get("objective") or ""),
            key_points=[item.strip() for item in str(filled_slots.get("key_points") or "").split("|") if item.strip()],
            source_basis=[item.strip() for item in str(filled_slots.get("__ppt_source_basis") or "").split("|") if item.strip()],
            source_excerpts=self._load_resume_source_excerpts(filled_slots=filled_slots),
            theme_id=str(filled_slots.get("theme_id") or ""),
            slide_count=slide_count,
        )

    def run(self, *, request, snapshot, decision):
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        append_debug_log(
            "ppt_workflow",
            event="runtime_run_started",
            echo=True,
            conversation_id=str(getattr(request, "conversation_id", "") or ""),
            question=str(getattr(request, "question", "") or ""),
            action_hint=str(getattr(request, "action_hint", "") or ""),
            workflow_type=str(getattr(workflow_state, "workflow_type", "") or ""),
            workflow_stage=str(getattr(workflow_state, "stage", "") or ""),
        )
        if workflow_state is not None and str(getattr(workflow_state, "workflow_type", "") or "").strip() == "ppt":
            workflow_stage = str(getattr(workflow_state, "stage", "") or "").strip()
            deck_artifact = _extract_artifact(workflow_state, "ppt_deck")
            deck_generation_state = dict((deck_artifact or {}).get("generation_state") or {}) if isinstance(deck_artifact, dict) else {}
            deck_running = str(deck_generation_state.get("status") or "").strip() == "running"
            if workflow_stage in {"submitting_ppt_job", "polling_ppt_job"} or deck_running:
                append_debug_log(
                    "ppt_workflow",
                    event="runtime_resume_existing_job",
                    echo=True,
                    conversation_id=str(getattr(request, "conversation_id", "") or ""),
                    workflow_stage=workflow_stage,
                )
                polled = self._poll_existing_job(request=request, workflow_state=workflow_state)
                if polled is not None:
                    return polled
            if workflow_stage == "awaiting_outline_confirmation":
                outline_artifact = _extract_artifact(workflow_state, "ppt_outline")
                affirmative = _is_affirmative_reply(request.question)
                append_debug_log(
                    "ppt_workflow",
                    event="runtime_awaiting_outline_confirmation",
                    echo=True,
                    conversation_id=str(getattr(request, "conversation_id", "") or ""),
                    question=str(getattr(request, "question", "") or ""),
                    affirmative=affirmative,
                    has_outline=outline_artifact is not None,
                )
                if outline_artifact is not None and affirmative:
                    preparation = self._build_resume_preparation(workflow_state=workflow_state)
                    followup_rounds = int(str((getattr(workflow_state, "filled_slots", {}) or {}).get("__ppt_followup_rounds") or "0") or 0)
                    outline = _normalize_outline_theme(PptOutline.model_validate(outline_artifact.get("content") or {}))
                    append_debug_log(
                        "ppt_workflow",
                        event="runtime_submit_confirmed_outline",
                        echo=True,
                        conversation_id=str(getattr(request, "conversation_id", "") or ""),
                        question=str(getattr(request, "question", "") or ""),
                        outline_summary=self._summarize_outline(outline),
                    )
                    return self._submit_outline(
                        request=request,
                        outline=outline,
                        preparation=preparation,
                        followup_rounds=followup_rounds,
                    )
                if outline_artifact is not None:
                    append_debug_log(
                        "ppt_workflow",
                        event="runtime_outline_confirmation_not_recognized",
                        echo=True,
                        conversation_id=str(getattr(request, "conversation_id", "") or ""),
                        question=str(getattr(request, "question", "") or ""),
                    )
                    return self._response(
                        request=request,
                        message="如果这版逐页大纲可以，就回复“确认”继续生成；如果要调整，也可以直接告诉我你想改哪几页或哪些重点。",
                        workflow={
                            "type": "ppt",
                            "status": "awaiting_confirm",
                            "phase": "awaiting_outline_confirmation",
                            "required_slots": [],
                            "filled_slots": dict(getattr(workflow_state, "filled_slots", {}) or {}),
                        },
                        artifacts=list(getattr(workflow_state, "artifacts", []) or []),
                        trace={"path": "workflow", "workflow_name": "ppt"},
                    )

        generation_context = self._build_generation_context(request=request, snapshot=snapshot)
        preparation = self.ppt_context_organizer.organize(
            context=generation_context,
            request_question=request.question,
        )
        followup_rounds = 0
        if workflow_state is not None and str(getattr(workflow_state, "workflow_type", "") or "").strip() == "ppt":
            followup_rounds = int(str((getattr(workflow_state, "filled_slots", {}) or {}).get("__ppt_followup_rounds") or "0") or 0)
        readiness_decision = self.readiness_judge.judge(preparation, followup_rounds=followup_rounds)
        append_debug_log(
            "ppt_workflow",
            event="runtime_preparation_ready",
            echo=True,
            conversation_id=str(getattr(request, "conversation_id", "") or ""),
            action=str(readiness_decision.get("action") or ""),
            followup_rounds=followup_rounds,
            topic=str(getattr(preparation, "topic", "") or ""),
            objective=str(getattr(preparation, "objective", "") or ""),
            key_points=list(getattr(preparation, "key_points", []) or []),
            preparation=preparation.model_dump(exclude_none=True),
            readiness_decision=readiness_decision,
        )
        if str(readiness_decision.get("action") or "").strip() == "ask_followup":
            return self._response(
                request=request,
                message=str(readiness_decision.get("followup_question") or readiness_decision.get("question") or preparation.followup_question or "").strip(),
                workflow={
                    "type": "ppt",
                    "status": "awaiting_confirm",
                    "phase": "collecting_inputs",
                    "required_slots": list(readiness_decision.get("required_slots") or []),
                    "filled_slots": _build_filled_slots(preparation=preparation, followup_rounds=followup_rounds + 1),
                },
                artifacts=[],
                trace={
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "ppt_preparation_result": preparation.model_dump(exclude_none=True),
                    "ppt_readiness_decision": readiness_decision,
                },
            )

        outline = self.outline_builder.build(preparation=preparation)
        append_debug_log(
            "ppt_workflow",
            event="runtime_outline_built",
            echo=True,
            conversation_id=str(getattr(request, "conversation_id", "") or ""),
            slide_count=len(list(outline.slides or [])),
            title=str(outline.deck_title or ""),
            outline_summary=self._summarize_outline(outline),
        )
        return self._response(
            request=request,
            message=f"我先整理出一版逐页 PPT 大纲，共 {len(list(outline.slides or []))} 页。请先确认这版结构，确认后我就继续生成 PPT。",
            workflow={
                "type": "ppt",
                "status": "awaiting_confirm",
                "phase": "awaiting_outline_confirmation",
                "required_slots": [],
                "filled_slots": _build_filled_slots(preparation=preparation, followup_rounds=followup_rounds),
            },
            artifacts=[_build_outline_artifact(conversation_id=request.conversation_id or "", outline=outline)],
            trace={
                "path": "workflow",
                "workflow_name": "ppt",
                "ppt_preparation_result": preparation.model_dump(exclude_none=True),
                "ppt_readiness_decision": readiness_decision,
                "ppt_outline_summary": self._summarize_outline(outline),
            },
        )

