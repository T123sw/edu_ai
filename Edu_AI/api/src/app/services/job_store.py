"""edu_ai 统一异步任务表（SPEC-05 §2.1）。

跟 `crawl_batch_store.py` 同一种文件持久化风格：每个 job 一个 JSON 文件，
落 `Config.STORAGE_ROOT/jobs/`。本轮只用到 `JobKind.GENERATE_CLASSROOM`，
`kind` 留作以后 parse_pdf/export_pptx/render_video/kg_build 等复用（SPEC-05 §2.1）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from core import Config


class JobKind(str, Enum):
    GENERATE_CLASSROOM = "generate_classroom"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EduJob(BaseModel):
    edu_job_id: str
    kind: JobKind
    sidecar_job_id: Optional[str] = None
    status: JobStatus = JobStatus.QUEUED
    step: str = "queued"
    progress: int = 0
    message: str = ""
    result_ref: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    owner: Optional[str] = None
    created_at: str
    updated_at: str


def _root() -> Path:
    path = Config.STORAGE_ROOT / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(edu_job_id: str) -> Path:
    return _root() / f"{edu_job_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(*, kind: JobKind, owner: Optional[str] = None) -> EduJob:
    now = _now()
    job = EduJob(
        edu_job_id=f"job_{uuid.uuid4().hex[:12]}",
        kind=kind,
        owner=owner,
        created_at=now,
        updated_at=now,
    )
    _write(job)
    return job


def get_job(edu_job_id: str) -> Optional[EduJob]:
    path = _path(edu_job_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return EduJob(**data)


def update_job(edu_job_id: str, **fields: Any) -> Optional[EduJob]:
    """按字段名局部更新；未传的字段保持原值。`updated_at` 总是刷新。"""
    job = get_job(edu_job_id)
    if job is None:
        return None
    updated = job.model_copy(update={**fields, "updated_at": _now()})
    _write(updated)
    return updated


def list_jobs(*, kind: Optional[JobKind] = None, limit: int = 20) -> list[EduJob]:
    files = sorted(_root().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    jobs: list[EduJob] = []
    for path in files:
        if len(jobs) >= max(1, int(limit or 20)):
            break
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            job = EduJob(**data)
        except Exception:
            continue
        if kind is not None and job.kind != kind:
            continue
        jobs.append(job)
    return jobs


def _write(job: EduJob) -> None:
    _path(job.edu_job_id).write_text(
        json.dumps(job.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
