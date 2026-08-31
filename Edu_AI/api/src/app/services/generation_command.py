"""Durable command boundary for teacher-facing generated resources."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.chat.tasks.task_store import TaskStore, get_task_store
from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    list_job_page,
    update_job,
)
from app.services.runtime_config_resolver import runtime_config_resolver
from app.services.generation_source_resolver import GenerationSourceMode


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
_WORKFLOW_BY_RESOURCE = {
    resource_type: f"{resource_type}_direct"
    for resource_type in _JOB_KIND_BY_RESOURCE
}


class GenerationCommand(BaseModel):
    resource_type: GenerationResourceType
    owner_user_id: str
    course_id: str
    scope_type: str = "course"
    scope_id: str | None = None
    source_mode: GenerationSourceMode = "course_auto"
    selected_doc_ids: list[str] = Field(default_factory=list)
    deadline_seconds: int = Field(default=300, ge=1, le=21600)
    config: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    material_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _infer_legacy_source_mode(cls, value):
        if isinstance(value, dict) and "source_mode" not in value:
            value = dict(value)
            value["source_mode"] = (
                "selected_documents"
                if value.get("selected_doc_ids")
                else "course_auto"
            )
        return value

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
        if self.source_mode == "selected_documents" and not self.selected_doc_ids:
            raise ValueError("selected_documents requires selected_doc_ids")
        if self.source_mode != "selected_documents" and self.selected_doc_ids:
            raise ValueError(
                "selected_doc_ids is only valid for selected_documents"
            )
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if len(self.idempotency_key) > 160:
            raise ValueError("idempotency_key is too long")
        if not str(self.material_id or "").strip():
            identity = json.dumps(
                {
                    "owner": self.owner_user_id,
                    "course": self.course_id,
                    "resource": self.resource_type,
                    "idempotency_key": self.idempotency_key,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
            self.material_id = f"{self.resource_type}-{digest}"
        else:
            self.material_id = str(self.material_id).strip()
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

    @property
    def workflow_type(self) -> str:
        return _WORKFLOW_BY_RESOURCE[self.resource_type]


class GenerationCommandService:
    _submission_lock = threading.RLock()

    def __init__(
        self,
        *,
        task_store: TaskStore | None = None,
        snapshot_provider: Callable[[str], dict[str, str]] | None = None,
    ) -> None:
        self.task_store = task_store or get_task_store()
        self.snapshot_provider = (
            snapshot_provider or runtime_config_resolver.capture_snapshot
        )

    def submit(
        self,
        command: GenerationCommand,
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
                        "title": str(
                            command.config.get("title")
                            or command.config.get("topic")
                            or command.resource_type
                        )[:160],
                        "resource_type": command.resource_type,
                        "source_mode": command.source_mode,
                        "selected_doc_ids": command.selected_doc_ids,
                        "config": command.config,
                        "config_snapshot_id": command.config_snapshot_id,
                        "idempotency_key": command.idempotency_key,
                        "source": "teacher-generation-factory",
                    },
                )
            else:
                job = existing_job

            payload = command.model_dump(mode="json")
            payload["runtime_config_snapshot"] = dict(
                self.snapshot_provider(command.owner_user_id)
            )
            if command.resource_type == "blog":
                payload["material_id"] = job.edu_job_id
            try:
                durable = self.task_store.enqueue(
                    task_id=job.edu_job_id,
                    workflow_type=command.workflow_type,
                    handler_version=1,
                    owner_user_id=command.owner_user_id,
                    course_id=command.course_id,
                    scope_type=command.scope_type,
                    scope_id=command.scope_id,
                    command=payload,
                    config_snapshot_id=command.config_snapshot_id,
                    idempotency_key=command.idempotency_key,
                    max_attempts=3,
                )
            except Exception as exc:
                failed = update_job(
                    job.edu_job_id,
                    status=JobStatus.FAILED,
                    step="enqueue_failed",
                    progress=100,
                    message="后台任务入队失败",
                    error_code="TASK_ENQUEUE_FAILED",
                    error_message=str(exc),
                )
                return failed or job

            if durable.task_id != job.edu_job_id:
                duplicate_job = get_job(durable.task_id)
                if duplicate_job is not None:
                    update_job(
                        job.edu_job_id,
                        status=JobStatus.FAILED,
                        step="duplicate_submission",
                        progress=100,
                        message="请求已由另一任务接收",
                        error_code="DUPLICATE_SUBMISSION",
                    )
                    return duplicate_job
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


generation_command_service = GenerationCommandService()
