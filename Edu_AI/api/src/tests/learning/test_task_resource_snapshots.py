from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.learning.service import LearningRuleError, LearningService
from app.learning.store import LearningStore


@dataclass(frozen=True)
class Membership:
    user_id: str
    role: str


def _memberships(_course_id: str):
    return [
        Membership("teacher-1", "owner"),
        Membership("student-1", "viewer"),
    ]


def test_standard_resource_snapshot_uses_approved_version_and_is_immutable(tmp_path) -> None:
    current = {
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "standard-leaf-study_guide",
        "title": "学习指南",
        "origin_type": "standard",
        "standard_kind": "study_guide",
        "visibility": "course",
        "version": 2,
        "approved_version": 1,
        "content": "pending version",
        "config_snapshot": {"prompt": "must not leak"},
    }
    approved = {
        **current,
        "version": 1,
        "content": "approved version",
    }
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *_args: dict(current),
        material_version_lookup=lambda *_args: dict(approved),
        membership_lookup=_memberships,
    )

    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        task_type="reading",
        title="阅读任务",
        instructions="完成学习指南",
        resource_refs=[
            {
                "material_type": "report",
                "material_id": "standard-leaf-study_guide",
            }
        ],
        knowledge_point_ids=["leaf"],
    )

    assert task.task_type == "reading"
    assert len(task.resource_snapshots) == 1
    snapshot = task.resource_snapshots[0]
    assert snapshot.source_version == 1
    assert snapshot.content_payload == {"content": "approved version"}
    assert "config_snapshot" not in snapshot.content_payload
    current["content"] = "changed later"
    loaded = service.list_tasks(
        course_id="course-1",
        user_id="student-1",
        include_unpublished=True,
    )[0].task
    assert loaded.resource_snapshots[0].content_payload["content"] == "approved version"


def test_teacher_can_snapshot_owned_personal_resource_but_not_another_users(tmp_path) -> None:
    material = {
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "personal-1",
        "title": "个人报告",
        "origin_type": "personal",
        "owner_user_id": "teacher-2",
        "visibility": "private",
        "version": 1,
        "content": "private",
    }
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *_args: material,
        membership_lookup=_memberships,
    )

    with pytest.raises(LearningRuleError) as error:
        service.create_task(
            course_id="course-1",
            teacher_id="teacher-1",
            task_type="reading",
            title="非法任务",
            instructions="",
            resource_refs=[
                {"material_type": "report", "material_id": "personal-1"}
            ],
            knowledge_point_ids=[],
        )

    assert error.value.code == "TASK_RESOURCE_FORBIDDEN"


def test_reading_task_completes_with_activity_evidence_after_all_snapshots(tmp_path) -> None:
    materials = {
        material_id: {
            "course_id": "course-1",
            "material_type": "report",
            "material_id": material_id,
            "title": material_id,
            "visibility": "course",
            "version": 1,
            "content": material_id,
        }
        for material_id in ("legacy-1", "legacy-2")
    }
    service = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda _course, _type, material_id, _user: materials.get(material_id),
        membership_lookup=_memberships,
    )
    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        task_type="reading",
        title="阅读任务",
        instructions="",
        resource_refs=[
            {"material_type": "report", "material_id": "legacy-1"},
            {"material_type": "report", "material_id": "legacy-2"},
        ],
        knowledge_point_ids=[],
    )
    service.publish_task(
        course_id="course-1", task_id=task.task_id, teacher_id="teacher-1"
    )

    first = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="complete-1",
        event_type="resource_completed",
        progress_percent=100,
        resource_ref=task.resource_refs[0],
    )
    assert first.progress.status == "in_progress"
    assert first.progress.completion_basis == "activity_evidenced"

    second = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="complete-2",
        event_type="resource_completed",
        progress_percent=100,
        resource_ref=task.resource_refs[1],
    )
    assert second.progress.status == "completed"
    assert second.progress.completion_basis == "activity_evidenced"
