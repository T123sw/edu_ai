from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import re
import time
from typing import Any

import httpx

from app.chat.debug_logging import append_debug_log
from app.chat.domain.ppt_outline import PptOutline
from app.chat.tasks.progress import report_progress

from .content_gate import PptContentGate
from .content_markdown_generator import PptContentMarkdownGenerator
from .content_validator import PptContentValidator
from .html2ppt_client import Html2PptClient
from .rag_image_bridge import extract_image_assets, inject_media_blocks

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


def _normalize_theme_id(value: str) -> str:
    text = str(value or "").strip()
    if text in _SUPPORTED_THEME_IDS:
        return text
    return _DEFAULT_THEME_ID


def normalize_outline_theme(outline: PptOutline) -> PptOutline:
    return outline.model_copy(update={"theme_id": _normalize_theme_id(outline.theme_id)})


def normalize_ppt_job_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "succeeded":
        return "completed"
    if normalized == "failed":
        return "failed"
    return "running"


def build_ppt_outline_artifact(*, artifact_scope_id: str, outline: PptOutline) -> dict[str, Any]:
    deck_title = str(outline.deck_title or "PPT Outline").strip() or "PPT Outline"
    return {
        "artifact_id": f"{artifact_scope_id or 'ppt'}:outline",
        "artifact_type": "ppt_outline",
        "title": f"{deck_title}-outline",
        "content": outline.model_dump(exclude_none=True),
        "generation_state": {
            "status": "awaiting_confirm",
            "phase": "awaiting_outline_confirmation",
        },
    }


def build_ppt_markdown_artifact(*, artifact_scope_id: str, outline: PptOutline, content_markdown: str) -> dict[str, Any]:
    deck_title = str(outline.deck_title or "PPT").strip() or "PPT"
    return {
        "artifact_id": f"{artifact_scope_id or 'ppt'}:content_markdown",
        "artifact_type": "ppt_content_markdown",
        "title": f"{deck_title}-content.md",
        "content": content_markdown,
        "generation_state": {
            "status": "completed",
            "phase": "assembling_content_markdown",
        },
    }


def build_ppt_deck_artifact(
    *,
    artifact_scope_id: str,
    outline: PptOutline,
    job_id: str,
    job_status_payload: dict[str, Any],
    results_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = normalize_ppt_job_status(job_status_payload.get("status"))
    try:
        resolved_slide_count = int((results_payload or {}).get("slide_count") or 0) if results_payload else 0
    except (TypeError, ValueError):
        resolved_slide_count = 0
    generation_state = {
        "status": normalized_status,
        "phase": str(job_status_payload.get("phase") or ("completed" if normalized_status == "completed" else "polling_ppt_job")),
        "progress": int(job_status_payload.get("progress") or (100 if normalized_status == "completed" else 0)),
        "message": str(job_status_payload.get("message") or ("PPT generation completed." if normalized_status == "completed" else "PPT is generating.")),
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
        "artifact_id": f"{artifact_scope_id or 'ppt'}:deck:{job_id}",
        "artifact_type": "ppt_deck",
        "title": f"{deck_title}.pptx",
        "content": content,
        "generation_state": generation_state,
    }


def build_html2ppt_metadata(*, request, content_markdown: str, theme_id: str) -> dict[str, str]:
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


def build_html2ppt_unreachable_message(exc: Exception) -> str:
    text = str(exc or "").strip()
    if "10061" in text or "actively refused" in text.lower():
        return "PPT 引擎当前未启动或未监听 `127.0.0.1:46080`。请先启动 html2ppt 服务，然后重新确认大纲。"
    return "PPT 引擎当前不可用，暂时无法继续生成。请先检查 html2ppt 服务是否已启动，然后重试。"


class PptPostOutlineExecutor:
    def __init__(
        self,
        *,
        content_markdown_generator: PptContentMarkdownGenerator | None = None,
        content_gate: PptContentGate | None = None,
        content_validator: PptContentValidator | None = None,
        html2ppt_client: Html2PptClient | None = None,
        html2ppt_client_factory=None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 600,
        max_poll_seconds: float = 1800.0,
        phase_poll_timeout_seconds: dict[str, float] | None = None,
    ) -> None:
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

    @property
    def html2ppt_client(self) -> Html2PptClient:
        if self._html2ppt_client is None and self._html2ppt_client_factory is not None:
            self._html2ppt_client = self._html2ppt_client_factory()
        if self._html2ppt_client is None:
            raise RuntimeError("html2ppt client is not configured")
        return self._html2ppt_client

    @staticmethod
    def _preview_text(value: object, limit: int = 280) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...(+{len(text) - limit} chars)"

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
                report_progress({
                    "html2ppt_job_id": job_id,
                    "phase": current_phase,
                    "progress": int(status_response.get("progress") or 0),
                })
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
        return timeout_status, None

    def execute(self, *, outline: PptOutline, request, metadata: dict[str, Any]) -> dict[str, Any]:
        artifact_scope_id = str(metadata.get("artifact_scope_id") or getattr(request, "conversation_id", "") or "ppt")
        outline = normalize_outline_theme(outline)
        preparation = metadata.get("preparation")
        content_markdown, content_generation_debug = self.content_markdown_generator.generate(
            outline=outline,
            preparation=preparation,
        )
        image_assets = extract_image_assets(list(getattr(preparation, "image_assets", []) or []))
        if image_assets:
            content_markdown = inject_media_blocks(content_markdown, image_assets, max_images=3)
        validation = self.content_gate.apply(content_markdown=content_markdown, outline=outline)
        final_markdown = str(validation.get("final_markdown") or content_markdown)
        artifacts = [
            build_ppt_outline_artifact(artifact_scope_id=artifact_scope_id, outline=outline),
            build_ppt_markdown_artifact(
                artifact_scope_id=artifact_scope_id,
                outline=outline,
                content_markdown=final_markdown,
            ),
        ]
        base_trace = {
            **dict(metadata.get("trace") or {}),
            "ppt_validation": validation,
            "ppt_content_generation_debug": content_generation_debug,
            "ppt_content_markdown": final_markdown,
        }

        if not bool(validation.get("ok")):
            return {
                "artifacts": artifacts,
                "status": "failed",
                "phase": "validating_content_markdown",
                "message": "PPT 协议稿生成失败，请调整后重试。",
                "trace": base_trace,
            }

        html2ppt_metadata = build_html2ppt_metadata(
            request=request,
            content_markdown=final_markdown,
            theme_id=outline.theme_id,
        )
        try:
            create_response = self.html2ppt_client.create_job(
                content_markdown=final_markdown,
                theme_id=outline.theme_id,
                metadata=html2ppt_metadata,
            )
        except httpx.RequestError as exc:
            return {
                "artifacts": artifacts,
                "status": "failed",
                "phase": "submitting_ppt_job",
                "message": build_html2ppt_unreachable_message(exc),
                "trace": {
                    **base_trace,
                    "html2ppt_error": {"type": exc.__class__.__name__, "message": str(exc)},
                },
            }

        job_id = str(create_response.get("job_id") or "").strip()
        if job_id:
            report_progress({"html2ppt_job_id": job_id, "phase": "submitted", "progress": 0})
        status_response = create_response if create_response.get("status") else {}
        results_response = None
        try:
            if job_id:
                status_response, results_response = self._wait_for_job_terminal_state(
                    request=request,
                    job_id=job_id,
                    initial_status=status_response,
                )
        except httpx.RequestError as exc:
            deck_artifact = build_ppt_deck_artifact(
                artifact_scope_id=artifact_scope_id,
                outline=outline,
                job_id=job_id,
                job_status_payload={
                    "status": "failed",
                    "phase": "polling_ppt_job",
                    "progress": 0,
                    "message": build_html2ppt_unreachable_message(exc),
                },
                results_payload=None,
            )
            return {
                "artifacts": artifacts + [deck_artifact],
                "status": "failed",
                "phase": "polling_ppt_job",
                "message": build_html2ppt_unreachable_message(exc),
                "trace": {
                    **base_trace,
                    "html2ppt_job": {"create_response": create_response},
                    "html2ppt_error": {"type": exc.__class__.__name__, "message": str(exc)},
                },
                "job_id": job_id,
            }

        deck_artifact = build_ppt_deck_artifact(
            artifact_scope_id=artifact_scope_id,
            outline=outline,
            job_id=job_id,
            job_status_payload=status_response or create_response,
            results_payload=results_response,
        )
        workflow_status = deck_artifact["generation_state"]["status"]
        workflow_phase = deck_artifact["generation_state"]["phase"]
        message = (
            "PPT 已生成完成，请在右侧查看和下载。"
            if workflow_status == "completed"
            else str(deck_artifact["generation_state"]["message"] or "PPT 已提交生成")
        )
        return {
            "artifacts": artifacts + [deck_artifact],
            "status": workflow_status,
            "phase": workflow_phase,
            "message": message,
            "trace": {
                **base_trace,
                "html2ppt_job": {
                    "create_response": create_response,
                    "status_response": status_response,
                    "results_response": results_response,
                },
            },
            "job_id": job_id,
            "run_id": f"ppt-run-{job_id}" if job_id else "",
        }
