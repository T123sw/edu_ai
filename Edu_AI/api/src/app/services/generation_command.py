"""Shared command boundary for teacher-facing generated resources.

The business generators stay independent.  This module owns the concerns that
must be identical for every entry point: validation, owner scoping,
idempotency, job lifecycle, configuration snapshots and persistence failures.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    JobKind,
    JobStatus,
    EduJob,
    create_job,
    list_job_page,
    update_job,
)


GenerationResourceType = Literal[
    "report",
    "lesson_plan",
    "blog",
    "quiz",
    "ppt",
    "flashcard",
    "graph",
    "game",
]

_JOB_KIND_BY_RESOURCE: dict[str, JobKind] = {
    "report": JobKind.GENERATE_REPORT,
    "lesson_plan": JobKind.GENERATE_LESSON_PLAN,
    "blog": JobKind.GENERATE_BLOG,
    "quiz": JobKind.GENERATE_QUIZ,
    "ppt": JobKind.GENERATE_PPT,
    "flashcard": JobKind.GENERATE_FLASHCARD,
    "graph": JobKind.GENERATE_GRAPH,
    "game": JobKind.GENERATE_GAME,
}


class GenerationCommand(BaseModel):
    resource_type: GenerationResourceType
    owner_user_id: str
    course_id: str
    scope_type: str = "course"
    scope_id: str | None = None
    selected_doc_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str

    @model_validator(mode="after")
    def _validate_required_context(self):
        self.owner_user_id = self.owner_user_id.strip()
        self.course_id = self.course_id.strip()
        self.scope_type = self.scope_type.strip() or "course"
        self.scope_id = str(self.scope_id or "").strip() or None
        self.idempotency_key = self.idempotency_key.strip()
        self.selected_doc_ids = list(
            dict.fromkeys(
                str(item or "").strip()
                for item in self.selected_doc_ids
                if str(item or "").strip()
            )
        )
        if not self.owner_user_id:
            raise ValueError("owner_user_id is required")
        if not self.course_id:
            raise ValueError("course_id is required")
        if not self.selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if len(self.idempotency_key) > 160:
            raise ValueError("idempotency_key is too long")
        return self

    @property
    def config_snapshot_id(self) -> str:
        payload = json.dumps(
            self.config,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return f"cfg_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


GenerationHandler = Callable[
    [GenerationCommand, str, str],
    dict[str, Any],
]


class GenerationCommandService:
    _submission_lock = threading.RLock()

    def submit(
        self,
        command: GenerationCommand,
        handler: GenerationHandler,
        *,
        existing_job: EduJob | None = None,
    ) -> EduJob:
        with self._submission_lock:
            if existing_job is None:
                duplicate = self._find_duplicate(command)
                if duplicate is not None:
                    return duplicate
                job = create_job(
                    kind=_JOB_KIND_BY_RESOURCE[command.resource_type],
                    owner_user_id=command.owner_user_id,
                    course_id=command.course_id,
                    scope_type=command.scope_type,
                    scope_id=command.scope_id,
                    input_summary={
                        "title": str(command.config.get("title") or command.resource_type)[:160],
                        "resource_type": command.resource_type,
                        "selected_doc_ids": command.selected_doc_ids,
                        "config": command.config,
                        "config_snapshot_id": command.config_snapshot_id,
                        "idempotency_key": command.idempotency_key,
                        "source": "teacher-generation-factory",
                    },
                )
            else:
                job = existing_job

            worker = threading.Thread(
                target=self._run,
                args=(job, command, handler),
                daemon=True,
                name=f"generation-{job.edu_job_id}",
            )
            worker.start()
            return job

    def _find_duplicate(self, command: GenerationCommand) -> EduJob | None:
        page = list_job_page(
            owner_user_id=command.owner_user_id,
            kinds=[_JOB_KIND_BY_RESOURCE[command.resource_type]],
            course_id=command.course_id,
            limit=200,
        )
        for job in page.items:
            if (
                str(job.input_summary.get("idempotency_key") or "")
                == command.idempotency_key
                and job.status
                in {
                    *ACTIVE_JOB_STATUSES,
                    JobStatus.SUCCEEDED,
                    JobStatus.PARTIALLY_SUCCEEDED,
                }
            ):
                return job
        return None

    @staticmethod
    def _run(
        job: EduJob,
        command: GenerationCommand,
        handler: GenerationHandler,
    ) -> None:
        update_job(
            job.edu_job_id,
            status=JobStatus.RUNNING,
            step="generating",
            progress=5,
            message="正在根据课程资料生成内容",
        )
        try:
            result = handler(
                command,
                job.edu_job_id,
                command.config_snapshot_id,
            )
            saved = bool(result.get("saved", True))
            result_ref = dict(result.get("result_ref") or {})
            if saved:
                update_job(
                    job.edu_job_id,
                    status=JobStatus.SUCCEEDED,
                    step="completed",
                    progress=100,
                    message="生成完成，结果已保存到课程资源",
                    result_ref=result_ref,
                )
            else:
                error = str(result.get("error") or "资源保存失败")
                update_job(
                    job.edu_job_id,
                    status=JobStatus.PARTIALLY_SUCCEEDED,
                    step="save_failed",
                    progress=100,
                    message="内容已生成，但保存课程资源失败",
                    result_ref=result_ref,
                    error_message=error,
                    error_code="RESOURCE_SAVE_FAILED",
                )
        except Exception as exc:  # worker boundary: publish a durable failure
            update_job(
                job.edu_job_id,
                status=JobStatus.FAILED,
                step="failed",
                progress=100,
                message="生成失败",
                error_message=str(exc),
                error_code="GENERATION_FAILED",
            )


generation_command_service = GenerationCommandService()

