"""Versioned, owner-scoped ledger for all long-running Edu AI jobs."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core import Config

log = logging.getLogger("job_store")


class JobKind(str, Enum):
    GENERATE_CLASSROOM = "generate_classroom"
    RENDER_VIDEO = "render_video"
    GENERATE_REPORT = "generate_report"
    GENERATE_LESSON_PLAN = "generate_lesson_plan"
    GENERATE_BLOG = "generate_blog"
    GENERATE_QUIZ = "generate_quiz"
    GENERATE_PPT = "generate_ppt"
    GENERATE_FLASHCARD = "generate_flashcard"
    GENERATE_GRAPH = "generate_graph"
    GENERATE_GAME = "generate_game"
    INGEST_VIDEO = "ingest_video"
    RAG_IMPORT = "rag_import"
    PARSE_DOCUMENT = "parse_document"
    BUILD_KNOWLEDGE_INDEX = "build_knowledge_index"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


ACTIVE_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCEL_REQUESTED,
}
RETRYABLE_JOB_STATUSES = {
    JobStatus.FAILED,
    JobStatus.PARTIALLY_SUCCEEDED,
    JobStatus.CANCELED,
}
TERMINAL_JOB_STATUSES = {
    JobStatus.SUCCEEDED,
    JobStatus.PARTIALLY_SUCCEEDED,
    JobStatus.FAILED,
    JobStatus.CANCELED,
}


def _normalize_result_ref(
    kind: JobKind, result_ref: Optional[dict[str, Any]], course_id: Optional[str]
) -> Optional[dict[str, Any]]:
    if not result_ref:
        return result_ref
    normalized = dict(result_ref)
    active_course_id = str(normalized.get("course_id") or course_id or "").strip()
    classroom_id = str(
        normalized.get("classroom_id") or normalized.get("material_id") or ""
    ).strip()
    if kind == JobKind.GENERATE_CLASSROOM and classroom_id and active_course_id:
        normalized.update(
            {
                "resource_type": "course_material",
                "course_id": active_course_id,
                "material_type": "classroom",
                "material_id": classroom_id,
                "classroom_id": classroom_id,
            }
        )
    elif kind == JobKind.RENDER_VIDEO and classroom_id and active_course_id:
        normalized.update(
            {
                "resource_type": "classroom_video",
                "course_id": active_course_id,
                "material_type": "classroom",
                "material_id": classroom_id,
                "classroom_id": classroom_id,
            }
        )
    return normalized


class EduJob(BaseModel):
    schema_version: int = 2
    version: int = 1
    edu_job_id: str
    kind: JobKind
    status: JobStatus = JobStatus.QUEUED
    step: str = "queued"
    progress: int = 0
    message: str = ""
    owner_user_id: str
    owner: Optional[str] = None
    course_id: Optional[str] = None
    scope_type: str = "course"
    scope_id: Optional[str] = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    result_ref: Optional[dict[str, Any]] = None
    retry_of_job_id: Optional[str] = None
    parent_job_id: Optional[str] = None
    provider_job_ref: Optional[dict[str, Any]] = None
    sidecar_job_id: Optional[str] = None
    error_message: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    retryable: bool = False
    cancelable: bool = True
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_record(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data.setdefault("schema_version", 1)
        owner = str(data.get("owner_user_id") or data.get("owner") or "").strip()
        data["owner_user_id"] = owner
        data["owner"] = owner or None
        error = data.get("error_message") or data.get("error")
        data["error_message"] = error
        data["error"] = error
        kind = JobKind(data.get("kind", JobKind.GENERATE_CLASSROOM))
        data["result_ref"] = _normalize_result_ref(
            kind, data.get("result_ref"), data.get("course_id")
        )
        if not data.get("course_id") and data.get("result_ref"):
            data["course_id"] = data["result_ref"].get("course_id")
        data.setdefault(
            "retryable", JobStatus(data.get("status", "queued")) in RETRYABLE_JOB_STATUSES
        )
        data.setdefault(
            "cancelable", JobStatus(data.get("status", "queued")) in ACTIVE_JOB_STATUSES
        )
        return data

    @field_validator("progress")
    @classmethod
    def _valid_progress(cls, value: int) -> int:
        return max(0, min(100, int(value)))


class JobListPage(BaseModel):
    items: list[EduJob]
    next_cursor: Optional[str] = None
    server_time: str


_ROOT_LOCKS: dict[str, threading.RLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()
_SENSITIVE_INPUT_MARKERS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
)


def _root() -> Path:
    path = Config.STORAGE_ROOT / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lock() -> threading.RLock:
    root_key = str(_root().resolve())
    with _ROOT_LOCKS_GUARD:
        return _ROOT_LOCKS.setdefault(root_key, threading.RLock())


def _path(edu_job_id: str) -> Path:
    safe_id = str(edu_job_id or "").strip()
    if not safe_id or Path(safe_id).name != safe_id:
        raise ValueError("invalid edu_job_id")
    return _root() / f"{safe_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_input(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_input(item)
            for key, item in value.items()
            if not any(
                marker in str(key).lower() for marker in _SENSITIVE_INPUT_MARKERS
            )
        }
    if isinstance(value, list):
        return [_sanitize_input(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def create_job(
    *,
    kind: JobKind,
    edu_job_id: Optional[str] = None,
    owner: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    input_summary: Optional[dict[str, Any]] = None,
    retry_of_job_id: Optional[str] = None,
    parent_job_id: Optional[str] = None,
) -> EduJob:
    now = _now()
    normalized_owner = str(owner_user_id or owner or "").strip()
    job = EduJob(
        schema_version=2,
        edu_job_id=str(edu_job_id or f"job_{uuid.uuid4().hex[:16]}"),
        kind=kind,
        owner_user_id=normalized_owner,
        owner=normalized_owner or None,
        course_id=str(course_id or "").strip() or None,
        scope_type=str(scope_type or "course").strip() or "course",
        scope_id=str(scope_id or "").strip() or None,
        input_summary=_sanitize_input(input_summary or {}),
        retry_of_job_id=retry_of_job_id,
        parent_job_id=parent_job_id,
        retryable=False,
        cancelable=True,
        created_at=now,
        updated_at=now,
    )
    with _lock():
        _write(job)
    return job


def get_job(edu_job_id: str) -> Optional[EduJob]:
    with _lock():
        return _read_path(_path(edu_job_id))


def update_job(
    edu_job_id: str, *, expected_version: Optional[int] = None, **fields: Any
) -> Optional[EduJob]:
    """Atomically update one job and reject stale optimistic writes."""
    with _lock():
        job = _read_path(_path(edu_job_id))
        if job is None:
            return None
        if expected_version is not None and job.version != expected_version:
            raise RuntimeError("job version conflict")

        patch = dict(fields)
        if "owner" in patch and "owner_user_id" not in patch:
            patch["owner_user_id"] = patch["owner"]
        if "owner_user_id" in patch:
            patch["owner"] = patch["owner_user_id"] or None
        if "error" in patch and "error_message" not in patch:
            patch["error_message"] = patch["error"]
        if "error_message" in patch:
            patch["error"] = patch["error_message"]
        if "input_summary" in patch:
            patch["input_summary"] = _sanitize_input(patch["input_summary"] or {})

        next_status = JobStatus(patch.get("status", job.status))
        if job.status == JobStatus.CANCEL_REQUESTED:
            if next_status in {JobStatus.RUNNING, JobStatus.SUCCEEDED, JobStatus.FAILED}:
                next_status = JobStatus.CANCELED
                patch["status"] = next_status
                patch["step"] = "canceled"
                patch["message"] = "任务已取消"
                patch["result_ref"] = None
        elif job.status in TERMINAL_JOB_STATUSES and next_status != job.status:
            raise ValueError("terminal job cannot transition to another status")

        now = _now()
        if next_status == JobStatus.RUNNING and not job.started_at:
            patch["started_at"] = now
        if next_status in TERMINAL_JOB_STATUSES:
            patch["finished_at"] = job.finished_at or now
            patch["cancelable"] = False
            patch["retryable"] = next_status in RETRYABLE_JOB_STATUSES
        elif next_status == JobStatus.CANCEL_REQUESTED:
            patch["cancelable"] = False

        result_ref = patch.get("result_ref", job.result_ref)
        patch["result_ref"] = _normalize_result_ref(
            job.kind, result_ref, patch.get("course_id", job.course_id)
        )
        patch["updated_at"] = now
        patch["version"] = job.version + 1
        updated = job.model_copy(update=patch)
        _write(updated)
        return updated


def reconcile_succeeded_job(
    edu_job_id: str,
    *,
    error_code: str,
    error_message: str,
) -> Optional[EduJob]:
    """Audit-only downgrade when a recorded result can no longer be read."""
    with _lock():
        job = _read_path(_path(edu_job_id))
        if job is None:
            return None
        if job.status != JobStatus.SUCCEEDED:
            return job
        now = _now()
        summary = dict(job.input_summary or {})
        summary["reconciled_from"] = JobStatus.SUCCEEDED.value
        updated = job.model_copy(
            update={
                "status": JobStatus.PARTIALLY_SUCCEEDED,
                "step": "resource_verification_failed",
                "progress": 100,
                "message": "任务曾完成，但结果资源当前无法读取",
                "input_summary": _sanitize_input(summary),
                "error_code": str(error_code or "RESOURCE_READBACK_FAILED"),
                "error_message": str(error_message or ""),
                "error": str(error_message or ""),
                "retryable": True,
                "cancelable": False,
                "updated_at": now,
                "version": job.version + 1,
            }
        )
        _write(updated)
        return updated


def list_job_page(
    *,
    owner_user_id: Optional[str] = None,
    statuses: Optional[Iterable[JobStatus]] = None,
    kinds: Optional[Iterable[JobKind]] = None,
    course_id: Optional[str] = None,
    active_only: bool = False,
    updated_after: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> JobListPage:
    normalized_limit = max(1, min(200, int(limit or 50)))
    try:
        offset = max(0, int(cursor or 0))
    except ValueError:
        raise ValueError("invalid cursor") from None
    status_filter = {JobStatus(value) for value in statuses or []}
    kind_filter = {JobKind(value) for value in kinds or []}

    with _lock():
        jobs = [
            job
            for path in _root().glob("*.json")
            if (job := _read_path(path)) is not None
        ]
    jobs.sort(key=lambda item: (item.updated_at, item.edu_job_id), reverse=True)
    filtered = [
        job
        for job in jobs
        if (owner_user_id is None or job.owner_user_id == owner_user_id)
        and (not status_filter or job.status in status_filter)
        and (not kind_filter or job.kind in kind_filter)
        and (course_id is None or job.course_id == course_id)
        and (not active_only or job.status in ACTIVE_JOB_STATUSES)
        and (updated_after is None or job.updated_at > updated_after)
    ]
    page_items = filtered[offset : offset + normalized_limit]
    next_offset = offset + len(page_items)
    return JobListPage(
        items=page_items,
        next_cursor=str(next_offset) if next_offset < len(filtered) else None,
        server_time=_now(),
    )


def list_jobs(
    *, kind: Optional[JobKind] = None, limit: int = 20
) -> list[EduJob]:
    return list_job_page(
        kinds=[kind] if kind is not None else None, limit=limit
    ).items


def cancel_job(edu_job_id: str, *, owner_user_id: str) -> EduJob:
    with _lock():
        job = _read_path(_path(edu_job_id))
        if job is None:
            raise KeyError(edu_job_id)
        _ensure_owner(job, owner_user_id)
        if not job.cancelable or job.status not in ACTIVE_JOB_STATUSES:
            raise ValueError("job cannot be canceled")
        status = (
            JobStatus.CANCELED
            if job.status == JobStatus.QUEUED
            else JobStatus.CANCEL_REQUESTED
        )
        updated = update_job(
            edu_job_id,
            status=status,
            step=status.value,
            message="任务取消中" if status == JobStatus.CANCEL_REQUESTED else "任务已取消",
        )
        assert updated is not None
        return updated


def retry_job(edu_job_id: str, *, owner_user_id: str) -> EduJob:
    with _lock():
        job = _read_path(_path(edu_job_id))
        if job is None:
            raise KeyError(edu_job_id)
        _ensure_owner(job, owner_user_id)
        if not job.retryable or job.status not in RETRYABLE_JOB_STATUSES:
            raise ValueError("job cannot be retried")
        return create_job(
            kind=job.kind,
            owner_user_id=owner_user_id,
            course_id=job.course_id,
            scope_type=job.scope_type,
            scope_id=job.scope_id,
            input_summary=job.input_summary,
            retry_of_job_id=job.edu_job_id,
            parent_job_id=job.parent_job_id,
        )


def _ensure_owner(job: EduJob, owner_user_id: str) -> None:
    if not job.owner_user_id or job.owner_user_id != owner_user_id:
        raise PermissionError("job owner mismatch")


def _read_path(path: Path) -> Optional[EduJob]:
    if not path.exists():
        return None
    try:
        return EduJob.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - one damaged record must not break the ledger
        log.warning("Skipping damaged job record %s: %s", path.name, exc)
        return None


def _write(job: EduJob) -> None:
    target = _path(job.edu_job_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        job.model_dump(mode="json"), ensure_ascii=False, indent=2
    ).encode("utf-8")
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.stem}-", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
