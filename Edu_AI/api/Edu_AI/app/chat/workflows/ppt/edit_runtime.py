from __future__ import annotations

import re
import time
from typing import Any

from .html2ppt_client import Html2PptClient

_SLIDE_PATTERNS = (
    re.compile(r"第\s*(\d+)\s*[页张]"),
    re.compile(r"\b(?:slide|page)\s*(\d+)\b", re.IGNORECASE),
)
_CHINESE_SLIDE_PATTERN = re.compile(r"第?([零一二两三四五六七八九十百]+)[页张]")
_CHINESE_NUMBER_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _parse_chinese_number(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    if text == "十":
        return 10
    if "百" in text:
        head, _, tail = text.partition("百")
        head_value = _CHINESE_NUMBER_MAP.get(head, 1) if head else 1
        tail_value = _parse_chinese_number(tail) if tail else 0
        return head_value * 100 + tail_value
    if "十" in text:
        head, _, tail = text.partition("十")
        head_value = _CHINESE_NUMBER_MAP.get(head, 1) if head else 1
        tail_value = _CHINESE_NUMBER_MAP.get(tail, 0) if tail else 0
        return head_value * 10 + tail_value
    return _CHINESE_NUMBER_MAP.get(text, 0)


def _normalize_reference(value) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: raw
            for key, raw in dict(vars(value)).items()
            if not key.startswith("_") and raw is not None
        }
    return {}


def _normalize_material_source(material: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    normalized = dict(material or {})
    content = dict(normalized.get("content") or {})
    outline = normalized.get("outline")
    source_artifact = {
        "artifact_id": normalized.get("material_id") or normalized.get("artifact_id") or "",
        "artifact_type": "ppt_deck",
        "title": normalized.get("title") or "PPT",
        "content": content,
        "generation_state": dict(normalized.get("generation_state") or {}),
    }
    outline_artifact = None
    if outline:
        outline_artifact = {
            "artifact_id": f"{source_artifact['artifact_id']}:outline",
            "artifact_type": "ppt_outline",
            "title": f"{str(source_artifact['title'] or 'PPT').replace('.pptx', '')}-大纲",
            "content": outline,
        }
    return source_artifact, outline_artifact


def _resolve_slide_numbers(question: str) -> list[int]:
    text = str(question or "")
    matches: list[int] = []
    for pattern in _SLIDE_PATTERNS:
        matches.extend(int(item) for item in pattern.findall(text))
    matches.extend(_parse_chinese_number(item) for item in _CHINESE_SLIDE_PATTERN.findall(text))
    unique: list[int] = []
    for value in matches:
        if value > 0 and value not in unique:
            unique.append(value)
    return unique


def _extract_slide_count(*, source_artifact: dict[str, Any], outline_artifact: dict[str, Any] | None) -> int:
    content = dict(source_artifact.get("content") or {})
    try:
        slide_count = int(content.get("slide_count") or 0)
    except (TypeError, ValueError):
        slide_count = 0
    if slide_count > 0:
        return slide_count
    slides = ((outline_artifact or {}).get("content") or {}).get("slides") if isinstance((outline_artifact or {}).get("content"), dict) else []
    return len(list(slides or []))


class PptEditRuntime:
    def __init__(
        self,
        *,
        html2ppt_client: Html2PptClient | None = None,
        html2ppt_client_factory=None,
        poll_interval_seconds: float = 1.0,
        max_poll_attempts: int = 1200,
    ) -> None:
        self._html2ppt_client = html2ppt_client
        self._html2ppt_client_factory = html2ppt_client_factory
        self.poll_interval_seconds = max(float(poll_interval_seconds or 0), 0.0)
        self.max_poll_attempts = max(int(max_poll_attempts or 1), 1)

    @property
    def html2ppt_client(self) -> Html2PptClient:
        if self._html2ppt_client is None and self._html2ppt_client_factory is not None:
            self._html2ppt_client = self._html2ppt_client_factory()
        if self._html2ppt_client is None:
            raise RuntimeError("html2ppt client is not configured")
        return self._html2ppt_client

    @staticmethod
    def _response(
        *,
        message: str,
        workflow_status: str,
        workflow_phase: str,
        artifacts: list[dict[str, Any]],
        trace: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "message": {"role": "assistant", "content": message},
            "conversation": {},
            "action": {"name": "ppt.edit"},
            "workflow": {"type": "ppt", "status": workflow_status, "phase": workflow_phase},
            "artifacts": artifacts,
            "sources": [],
            "trace": trace,
        }

    @staticmethod
    def _current_artifacts(*, source_artifact: dict[str, Any], outline_artifact: dict[str, Any] | None) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        if outline_artifact:
            artifacts.append(outline_artifact)
        artifacts.append(source_artifact)
        return artifacts

    @staticmethod
    def _build_updated_deck_artifact(
        *,
        source_artifact: dict[str, Any],
        target_slide: int,
        revision_id: str,
        results_payload: dict[str, Any],
    ) -> dict[str, Any]:
        source_content = dict(source_artifact.get("content") or {})
        next_results = dict((results_payload or {}).get("results") or {})
        next_content = {
            **next_results,
            "job_id": str(source_content.get("job_id") or "").strip(),
            "revision_id": revision_id,
        }
        if source_content.get("theme_id"):
            next_content["theme_id"] = source_content.get("theme_id")
        try:
            refreshed_slide_count = int((results_payload or {}).get("slide_count") or 0)
        except (TypeError, ValueError):
            refreshed_slide_count = 0
        if refreshed_slide_count > 0:
            next_content["slide_count"] = refreshed_slide_count
        elif source_content.get("slide_count"):
            next_content["slide_count"] = source_content.get("slide_count")

        return {
            "artifact_id": f"{str(source_artifact.get('artifact_id') or '').strip()}:{revision_id}",
            "artifact_type": "ppt_deck",
            "title": str(source_artifact.get("title") or "PPT").strip() or "PPT",
            "content": next_content,
            "generation_state": {
                "status": "completed",
                "phase": "completed",
                "progress": 100,
                "message": "PPT 已修改完成",
                "generation_mode": "revise_ppt",
                "source_deck_artifact_id": str(source_artifact.get("artifact_id") or "").strip(),
                "source_revision_id": str(source_content.get("revision_id") or "").strip(),
                "target_slide_index": target_slide,
            },
        }

    @staticmethod
    def _build_pending_deck_artifact(
        *,
        source_artifact: dict[str, Any],
        target_slide: int,
        pending_revision_id: str,
    ) -> dict[str, Any]:
        source_content = dict(source_artifact.get("content") or {})
        next_content = dict(source_content)
        return {
            "artifact_id": str(source_artifact.get("artifact_id") or "").strip(),
            "artifact_type": "ppt_deck",
            "title": str(source_artifact.get("title") or "PPT").strip() or "PPT",
            "content": next_content,
            "generation_state": {
                "status": "running",
                "phase": "polling_revision",
                "progress": 10,
                "message": "PPT 正在修改中",
                "generation_mode": "revise_ppt",
                "source_deck_artifact_id": str(source_artifact.get("artifact_id") or "").strip(),
                "source_revision_id": str(source_content.get("revision_id") or "").strip(),
                "pending_revision_id": pending_revision_id,
                "target_slide_index": target_slide,
            },
        }

    @staticmethod
    def _find_snapshot_artifact(*, snapshot, artifact_id: str, artifact_type: str | None = None) -> dict[str, Any] | None:
        workflow_state = getattr(snapshot, "workflow_state", None)
        artifacts = list(getattr(workflow_state, "artifacts", []) or []) if workflow_state is not None else []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            if artifact_type and str(artifact.get("artifact_type") or "").strip() != artifact_type:
                continue
            if str(artifact.get("artifact_id") or "").strip() == artifact_id:
                return dict(artifact)
        return None

    @staticmethod
    def _find_outline_artifact(*, snapshot) -> dict[str, Any] | None:
        workflow_state = getattr(snapshot, "workflow_state", None)
        artifacts = list(getattr(workflow_state, "artifacts", []) or []) if workflow_state is not None else []
        for artifact in artifacts:
            if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "ppt_outline":
                return dict(artifact)
        return None

    def _refresh_slide_count_from_results(self, *, source_artifact: dict[str, Any]) -> int:
        content = dict(source_artifact.get("content") or {})
        job_id = str(content.get("job_id") or "").strip()
        if not job_id:
            return 0
        try:
            results_payload = dict(self.html2ppt_client.get_job_results(job_id) or {})
        except Exception:
            return 0

        try:
            refreshed_slide_count = int(results_payload.get("slide_count") or 0)
        except (TypeError, ValueError):
            refreshed_slide_count = 0
        if refreshed_slide_count <= 0:
            return 0

        next_content = {
            **content,
            **dict(results_payload.get("results") or {}),
            "slide_count": refreshed_slide_count,
        }
        latest_revision_id = str(results_payload.get("latest_revision_id") or "").strip()
        if latest_revision_id:
            next_content["revision_id"] = latest_revision_id
        source_artifact["content"] = next_content
        return refreshed_slide_count

    def _wait_for_revision_terminal_state(self, *, job_id: str, revision_id: str) -> dict[str, Any]:
        last_status: dict[str, Any] = {}
        for attempt in range(1, self.max_poll_attempts + 1):
            last_status = dict(self.html2ppt_client.get_revision_status(job_id, revision_id) or {})
            normalized_status = str(last_status.get("status") or "").strip().lower()
            if normalized_status in {"completed", "succeeded", "failed", "error"}:
                return last_status
            if attempt < self.max_poll_attempts and self.poll_interval_seconds > 0:
                time.sleep(self.poll_interval_seconds)
        return {
            **last_status,
            "revision_id": revision_id,
            "status": "failed",
            "message": "PPT revision timed out before completion.",
        }

    def _resume_revision(
        self,
        *,
        source_artifact: dict[str, Any],
        outline_artifact: dict[str, Any] | None,
        pending_revision_id: str,
        target_slide: int,
    ) -> dict[str, Any]:
        source_content = dict(source_artifact.get("content") or {})
        job_id = str(source_content.get("job_id") or "").strip()
        source_revision_id = str(
            ((source_artifact.get("generation_state") or {}).get("source_revision_id"))
            or source_content.get("revision_id")
            or ""
        ).strip()
        revision_status = dict(self.html2ppt_client.get_revision_status(job_id, pending_revision_id) or {})
        normalized_status = str(revision_status.get("status") or "").strip().lower()

        if normalized_status in {"completed", "succeeded"}:
            results_payload = dict(self.html2ppt_client.get_job_results(job_id) or {})
            latest_revision_id = str(results_payload.get("latest_revision_id") or pending_revision_id).strip() or pending_revision_id
            next_deck_artifact = self._build_updated_deck_artifact(
                source_artifact=source_artifact,
                target_slide=target_slide,
                revision_id=latest_revision_id,
                results_payload=results_payload,
            )
            artifacts = []
            if outline_artifact:
                artifacts.append(outline_artifact)
            artifacts.append(next_deck_artifact)
            return self._response(
                message="PPT 已修改完成，请在右侧查看和导出。",
                workflow_status="completed",
                workflow_phase="completed",
                artifacts=artifacts,
                trace={
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "artifact_edit": {"target_slide": target_slide, "source_revision_id": source_revision_id},
                    "html2ppt_revision": revision_status,
                    "html2ppt_results": results_payload,
                },
            )

        if normalized_status in {"failed", "error"}:
            return self._response(
                message=str(revision_status.get("message") or "PPT 修改失败，请稍后重试。").strip() or "PPT 修改失败，请稍后重试。",
                workflow_status="failed",
                workflow_phase=str(revision_status.get("phase") or "polling_revision").strip() or "polling_revision",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "artifact_edit": {"target_slide": target_slide, "source_revision_id": source_revision_id},
                    "html2ppt_revision": revision_status,
                },
            )

        return self._response(
            message=f"已开始修改第 {target_slide} 页，正在处理中。",
            workflow_status="running",
            workflow_phase="polling_revision",
            artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
            trace={
                "path": "workflow",
                "workflow_name": "ppt",
                "artifact_edit": {"target_slide": target_slide, "source_revision_id": source_revision_id},
                "html2ppt_revision": revision_status,
            },
        )

    def run(
        self,
        *,
        question: str,
        artifact_reference: dict[str, Any],
        source_artifact: dict[str, Any],
        outline_artifact: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact_reference = _normalize_reference(artifact_reference)
        source_artifact = dict(source_artifact or {})
        source_artifact["artifact_type"] = str(source_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or "").strip()

        if str(source_artifact.get("artifact_type") or "").strip() != "ppt_deck":
            return self._response(
                message="当前仅支持修改已生成完成的 PPT 文件，请先引用最终 PPT 后再继续。",
                workflow_status="failed",
                workflow_phase="artifact_edit_validation",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "unsupported_artifact_type"}},
            )

        content = dict(source_artifact.get("content") or {})
        job_id = str(content.get("job_id") or "").strip()
        source_revision_id = str(content.get("revision_id") or "").strip()
        if not job_id or not source_revision_id:
            return self._response(
                message="当前 PPT 缺少可修改上下文，请重新生成后再修改。",
                workflow_status="failed",
                workflow_phase="artifact_edit_validation",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "missing_job_or_revision_id"}},
            )

        target_slides = _resolve_slide_numbers(question)
        slide_count = _extract_slide_count(source_artifact=source_artifact, outline_artifact=outline_artifact)
        refreshed_slide_count = self._refresh_slide_count_from_results(source_artifact=source_artifact)
        if refreshed_slide_count > 0:
            slide_count = refreshed_slide_count
        if not target_slides:
            return self._response(
                message='已引用当前 PPT。请直接说明要修改哪一页，例如“把第 3 页改成流程图风格”。',
                workflow_status="awaiting_input",
                workflow_phase="awaiting_revision_target",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "missing_target_slide"}},
            )
        if len(target_slides) > 1:
            return self._response(
                message='这次修改请先只指定 1 页，例如“把第 3 页改成流程图风格”。',
                workflow_status="awaiting_input",
                workflow_phase="awaiting_revision_target",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "multiple_target_slides", "target_slides": target_slides}},
            )
        target_slide = target_slides[0]
        if slide_count > 0 and target_slide > slide_count:
            refreshed_slide_count = self._refresh_slide_count_from_results(source_artifact=source_artifact)
            if refreshed_slide_count > 0:
                slide_count = refreshed_slide_count
        if slide_count > 0 and target_slide > slide_count:
            return self._response(
                message=f"当前 PPT 共有 {slide_count} 页，请指定一个有效页码后再试。",
                workflow_status="awaiting_input",
                workflow_phase="awaiting_revision_target",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "slide_out_of_range", "target_slide": target_slide, "slide_count": slide_count}},
            )

        revision_response = self.html2ppt_client.create_revision(
            job_id,
            mode="single_slide",
            target_slides=[target_slide],
            user_instruction=question,
            metadata={
                "source_revision_id": source_revision_id,
                "source_artifact_id": str(source_artifact.get("artifact_id") or "").strip(),
            },
        )
        revision_id = str(revision_response.get("revision_id") or "").strip()
        if not revision_id:
            return self._response(
                message="PPT 修改请求未返回 revision_id，请稍后重试。",
                workflow_status="failed",
                workflow_phase="submitting_revision",
                artifacts=self._current_artifacts(source_artifact=source_artifact, outline_artifact=outline_artifact),
                trace={"path": "workflow", "workflow_name": "ppt", "artifact_edit": {"reason": "missing_revision_id"}},
            )

        pending_deck_artifact = self._build_pending_deck_artifact(
            source_artifact=source_artifact,
            target_slide=target_slide,
            pending_revision_id=revision_id,
        )
        artifacts = []
        if outline_artifact:
            artifacts.append(outline_artifact)
        artifacts.append(pending_deck_artifact)
        return self._response(
            message=f"已开始修改第 {target_slide} 页，正在处理中。",
            workflow_status="running",
            workflow_phase="polling_revision",
            artifacts=artifacts,
            trace={
                "path": "workflow",
                "workflow_name": "ppt",
                "artifact_edit": {"target_slide": target_slide, "source_revision_id": source_revision_id},
                "html2ppt_revision": revision_response,
            },
        )

    def resume_from_snapshot(self, *, request, snapshot, course_storage_manager=None):
        workflow_state = getattr(snapshot, "workflow_state", None)
        if workflow_state is None:
            return None
        if str(getattr(workflow_state, "workflow_type", "") or "").strip() != "ppt":
            return None
        if str(getattr(workflow_state, "status", "") or "").strip() != "running":
            return None
        if str(getattr(workflow_state, "stage", "") or "").strip() != "polling_revision":
            return None

        artifact_reference = _normalize_reference(getattr(request, "artifact_reference", None))
        artifact_id = str(artifact_reference.get("artifact_id") or "").strip()
        source_artifact = self._find_snapshot_artifact(snapshot=snapshot, artifact_id=artifact_id, artifact_type="ppt_deck")
        outline_artifact = self._find_outline_artifact(snapshot=snapshot)

        if source_artifact is None and course_storage_manager is not None:
            course_id = str(getattr(request, "course_id", "") or "").strip()
            if course_id and artifact_id:
                material = course_storage_manager.get_generated_material(course_id, "ppt", artifact_id)
                if material:
                    source_artifact, outline_artifact = _normalize_material_source(material)
                    source_artifact["artifact_id"] = artifact_id
                    source_artifact["title"] = artifact_reference.get("title") or source_artifact.get("title")

        if source_artifact is None:
            return None

        generation_state = dict(source_artifact.get("generation_state") or {})
        if str(generation_state.get("generation_mode") or "").strip() != "revise_ppt":
            return None
        pending_revision_id = str(generation_state.get("pending_revision_id") or "").strip()
        target_slide = int(generation_state.get("target_slide_index") or 0)
        if not pending_revision_id or target_slide <= 0:
            return None

        return self._resume_revision(
            source_artifact=source_artifact,
            outline_artifact=outline_artifact,
            pending_revision_id=pending_revision_id,
            target_slide=target_slide,
        )

    def run_from_request(self, *, request, snapshot, course_storage_manager):
        artifact_reference = _normalize_reference(getattr(request, "artifact_reference", None))
        if not artifact_reference:
            raise ValueError("artifact_reference is required")

        source_artifact = None
        outline_artifact = None
        course_id = str(getattr(request, "course_id", "") or "").strip()
        artifact_id = str(artifact_reference.get("artifact_id") or "").strip()
        if course_storage_manager is not None and course_id and artifact_id:
            material = course_storage_manager.get_generated_material(course_id, "ppt", artifact_id)
            if material:
                source_artifact, outline_artifact = _normalize_material_source(material)
                source_artifact["artifact_id"] = artifact_id
                source_artifact["title"] = artifact_reference.get("title") or source_artifact.get("title")

        if source_artifact is None and snapshot is not None:
            source_artifact = self._find_snapshot_artifact(snapshot=snapshot, artifact_id=artifact_id, artifact_type="ppt_deck")
            outline_artifact = self._find_outline_artifact(snapshot=snapshot)

        if source_artifact is None:
            raise ValueError("referenced artifact not found")

        return self.run(
            question=str(getattr(request, "question", "") or ""),
            artifact_reference=artifact_reference,
            source_artifact=source_artifact,
            outline_artifact=outline_artifact,
        )
