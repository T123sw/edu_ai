"""Business rules and role-specific projections for course learning."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict
from typing import Any

from .models import (
    CourseTaskSummaryRecord,
    LearningEventRecord,
    LearningEventType,
    LearningTaskRecord,
    LearningTaskView,
    TaskProgressRecord,
    utc_now,
)
from .store import EventWriteResult, LearningStore


MaterialLookup = Callable[[str, str, str, str], dict[str, Any] | None]
MembershipLookup = Callable[[str], Iterable[Any]]


class LearningRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _membership_value(membership: Any, field: str) -> str:
    if isinstance(membership, dict):
        return str(membership.get(field, "")).strip()
    return str(getattr(membership, field, "")).strip()


class LearningService:
    def __init__(
        self,
        *,
        store: LearningStore,
        material_lookup: MaterialLookup,
        membership_lookup: MembershipLookup,
    ):
        self.store = store
        self.material_lookup = material_lookup
        self.membership_lookup = membership_lookup

    @staticmethod
    def _require_text(value: str, *, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise LearningRuleError("INVALID_TASK", f"{field} is required")
        return normalized

    def _task_or_error(self, *, course_id: str, task_id: str) -> LearningTaskRecord:
        task = self.store.get_task(task_id, course_id=course_id)
        if task is None:
            raise LearningRuleError("TASK_NOT_FOUND", "Learning task was not found")
        return task

    def _teacher_membership(self, *, course_id: str, teacher_id: str) -> Any:
        for membership in self.membership_lookup(course_id):
            if (
                _membership_value(membership, "user_id") == teacher_id
                and _membership_value(membership, "role") in {"owner", "editor"}
            ):
                return membership
        raise LearningRuleError("COURSE_EDIT_REQUIRED", "Course edit permission is required")

    def _student_ids(self, course_id: str) -> list[str]:
        return sorted(
            {
                _membership_value(membership, "user_id")
                for membership in self.membership_lookup(course_id)
                if _membership_value(membership, "role") == "viewer"
                and _membership_value(membership, "user_id")
            }
        )

    def _validate_resource_refs(
        self,
        *,
        course_id: str,
        teacher_id: str,
        resource_refs: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        validated: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for raw_ref in resource_refs:
            material_type = str(raw_ref.get("material_type", "")).strip()
            material_id = str(raw_ref.get("material_id", "")).strip()
            if not material_type or not material_id:
                raise LearningRuleError("INVALID_RESOURCE_REF", "Resource reference is incomplete")
            key = (material_type, material_id)
            if key in seen:
                continue
            material = self.material_lookup(course_id, material_type, material_id, teacher_id)
            if not material or str(material.get("visibility", "")) != "course":
                raise LearningRuleError(
                    "COURSE_RESOURCE_NOT_FOUND",
                    "Only resources shared with this course can be assigned",
                )
            seen.add(key)
            validated.append({"material_type": material_type, "material_id": material_id})
        return validated

    def create_task(
        self,
        *,
        course_id: str,
        teacher_id: str,
        title: str,
        instructions: str,
        resource_refs: list[dict[str, str]],
        knowledge_point_ids: list[str],
    ) -> LearningTaskRecord:
        self._teacher_membership(course_id=course_id, teacher_id=teacher_id)
        task = LearningTaskRecord.new(
            course_id=self._require_text(course_id, field="course_id"),
            title=self._require_text(title, field="title"),
            instructions=str(instructions or "").strip(),
            created_by=self._require_text(teacher_id, field="teacher_id"),
            resource_refs=self._validate_resource_refs(
                course_id=course_id,
                teacher_id=teacher_id,
                resource_refs=resource_refs,
            ),
            knowledge_point_ids=list(dict.fromkeys(
                str(item).strip() for item in knowledge_point_ids if str(item).strip()
            )),
        )
        return self.store.create_task(task)

    def publish_task(
        self,
        *,
        course_id: str,
        task_id: str,
        teacher_id: str,
    ) -> LearningTaskRecord:
        self._teacher_membership(course_id=course_id, teacher_id=teacher_id)
        self._task_or_error(course_id=course_id, task_id=task_id)
        try:
            return self.store.publish_task(task_id, course_id=course_id, published_by=teacher_id)
        except KeyError as exc:
            raise LearningRuleError("TASK_NOT_PUBLISHABLE", "Task cannot be published") from exc

    def list_tasks(
        self,
        *,
        course_id: str,
        user_id: str,
        include_unpublished: bool,
        limit: int | None = None,
    ) -> list[LearningTaskView]:
        statuses = None if include_unpublished else {"published"}
        tasks = self.store.list_tasks(course_id, statuses=statuses, limit=limit)
        return [
            LearningTaskView(
                task=task,
                my_progress=self.store.get_progress(task.task_id, user_id),
            )
            for task in tasks
        ]

    def record_student_event(
        self,
        *,
        course_id: str,
        task_id: str,
        student_id: str,
        event_id: str,
        event_type: LearningEventType,
        progress_percent: int,
        resource_ref: dict[str, str] | None,
    ) -> EventWriteResult:
        task = self._task_or_error(course_id=course_id, task_id=task_id)
        if task.status != "published":
            raise LearningRuleError("TASK_NOT_PUBLISHED", "Only published tasks accept learning events")
        if not 0 <= int(progress_percent) <= 100:
            raise LearningRuleError("INVALID_PROGRESS", "Progress must be between 0 and 100")
        normalized_ref = None
        if resource_ref:
            normalized_ref = {
                "material_type": str(resource_ref.get("material_type", "")).strip(),
                "material_id": str(resource_ref.get("material_id", "")).strip(),
            }
            if normalized_ref not in task.resource_refs:
                raise LearningRuleError("RESOURCE_NOT_ASSIGNED", "Resource is not attached to this task")
        event = LearningEventRecord.new(
            event_id=self._require_text(event_id, field="event_id"),
            course_id=course_id,
            task_id=task_id,
            student_id=self._require_text(student_id, field="student_id"),
            event_type=event_type,
            progress_percent=progress_percent,
            resource_ref=normalized_ref,
        )
        return self.store.record_event(event)

    def get_task_summary(
        self,
        *,
        course_id: str,
        task_id: str,
        teacher_id: str,
    ) -> CourseTaskSummaryRecord:
        self._teacher_membership(course_id=course_id, teacher_id=teacher_id)
        task = self._task_or_error(course_id=course_id, task_id=task_id)
        progress_by_student = {
            item.student_id: item for item in self.store.list_progress(course_id=course_id, task_id=task_id)
        }
        now = utc_now()
        progress = [
            progress_by_student.get(student_id)
            or TaskProgressRecord(
                task_id=task_id,
                course_id=course_id,
                student_id=student_id,
                status="not_started",
                progress_percent=0,
                started_at=None,
                completed_at=None,
                updated_at=now,
            )
            for student_id in self._student_ids(course_id)
        ]
        started = sum(item.status != "not_started" for item in progress)
        completed = sum(item.status == "completed" for item in progress)
        enrolled = len(progress)
        return CourseTaskSummaryRecord(
            task=task,
            enrolled_students=enrolled,
            started_students=started,
            completed_students=completed,
            completion_rate=completed / enrolled if enrolled else 0.0,
            progress=progress,
        )

    def get_student_agent_context(
        self,
        *,
        course_id: str,
        student_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        views = self.list_tasks(
            course_id=course_id,
            user_id=student_id,
            include_unpublished=False,
            limit=limit,
        )
        items = [
            {
                "task_id": view.task.task_id,
                "title": view.task.title,
                "instructions": view.task.instructions,
                "resource_refs": [dict(item) for item in view.task.resource_refs],
                "knowledge_point_ids": list(view.task.knowledge_point_ids),
                "status": view.my_progress.status if view.my_progress else "not_started",
                "progress_percent": view.my_progress.progress_percent if view.my_progress else 0,
            }
            for view in views
        ]
        return {
            "projection": "student",
            "pending_tasks": [item for item in items if item["status"] != "completed"],
            "completed_tasks": [item for item in items if item["status"] == "completed"],
        }

    def get_teacher_agent_context(
        self,
        *,
        course_id: str,
        teacher_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        self._teacher_membership(course_id=course_id, teacher_id=teacher_id)
        tasks = self.store.list_tasks(course_id, statuses={"published"}, limit=limit)
        summaries = [
            self.get_task_summary(course_id=course_id, task_id=task.task_id, teacher_id=teacher_id)
            for task in tasks
        ]
        return {
            "projection": "teacher",
            "task_summaries": [
                {
                    **asdict(summary.task),
                    "enrolled_students": summary.enrolled_students,
                    "started_students": summary.started_students,
                    "completed_students": summary.completed_students,
                    "completion_rate": summary.completion_rate,
                }
                for summary in summaries
            ],
        }
