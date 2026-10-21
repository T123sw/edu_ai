"""Classroom job identities and source intent, independent of the renderer."""
from dataclasses import dataclass
from typing import Any, Optional
from app.services.generation_source_resolver import GenerationSourceMode
from app.services.job_store import EduJob, JobKind, create_job

@dataclass(frozen=True)
class ClassroomSourceIntent:
    mode: GenerationSourceMode
    selected_document_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        mode: GenerationSourceMode,
        selected_document_ids: list[str] | tuple[str, ...],
    ) -> "ClassroomSourceIntent":
        normalized = tuple(
            dict.fromkeys(
                str(item or "").strip()
                for item in selected_document_ids
                if str(item or "").strip()
            )
        )
        if mode == "selected_documents" and not normalized:
            raise ValueError("selected_documents requires at least one document")
        if mode != "selected_documents" and normalized:
            raise ValueError(
                "selected_doc_ids is only valid for selected_documents"
            )
        return cls(mode=mode, selected_document_ids=normalized)


def create_classroom_job(
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    input_summary: Optional[dict[str, Any]] = None,
) -> EduJob:
    """只建 job（queued），交给持久任务 worker。给需要"立即拿到 edu_job_id 再
    在后台跑生成"的调用方用（P3-2 异步提交），见
    `classroom_service.submit_classroom_generation_job`。"""
    return create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id=owner,
        course_id=course_id,
        scope_type=scope_type,
        scope_id=scope_id,
        input_summary=input_summary,
    )
