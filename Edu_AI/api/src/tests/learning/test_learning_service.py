from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.learning.service import LearningRuleError, LearningService
from app.learning.store import LearningStore


@dataclass(frozen=True)
class Membership:
    user_id: str
    role: str


@pytest.fixture
def material_lookup():
    materials = {
        ("course-1", "report", "report-1"): {
            "material_id": "report-1",
            "material_type": "report",
            "visibility": "course",
        },
        ("course-1", "report", "private-1"): {
            "material_id": "private-1",
            "material_type": "report",
            "visibility": "private",
        },
    }

    def lookup(course_id: str, material_type: str, material_id: str, user_id: str):
        del user_id
        return materials.get((course_id, material_type, material_id))

    return lookup


@pytest.fixture
def membership_lookup():
    def lookup(course_id: str):
        if course_id != "course-1":
            return []
        return [
            Membership("teacher-1", "owner"),
            Membership("student-1", "viewer"),
            Membership("student-2", "viewer"),
        ]

    return lookup


@pytest.fixture
def service(tmp_path, material_lookup, membership_lookup):
    return LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=material_lookup,
        membership_lookup=membership_lookup,
    )


def _create_task(service: LearningService, *, resource_refs=None):
    return service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        title="学习快速排序",
        instructions="阅读材料并完成学习",
        resource_refs=resource_refs or [],
        knowledge_point_ids=["quick-sort"],
    )


def test_student_cannot_record_event_for_draft_task(service):
    task = _create_task(service)

    with pytest.raises(LearningRuleError) as error:
        service.record_student_event(
            course_id="course-1",
            task_id=task.task_id,
            student_id="student-1",
            event_id="evt-1",
            event_type="started",
            progress_percent=1,
            resource_ref=None,
        )

    assert error.value.code == "TASK_NOT_PUBLISHED"


@pytest.mark.parametrize("material_id", ["missing", "private-1"])
def test_task_rejects_missing_or_private_material(service, material_id):
    with pytest.raises(LearningRuleError) as error:
        _create_task(
            service,
            resource_refs=[
                {"material_type": "report", "material_id": material_id}
            ],
        )

    assert error.value.code == "COURSE_RESOURCE_NOT_FOUND"


def test_student_lists_only_published_tasks_with_own_progress(service):
    draft = _create_task(service)
    published = _create_task(
        service,
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
    )
    service.publish_task(
        course_id="course-1",
        task_id=published.task_id,
        teacher_id="teacher-1",
    )
    service.record_student_event(
        course_id="course-1",
        task_id=published.task_id,
        student_id="student-1",
        event_id="evt-start",
        event_type="started",
        progress_percent=10,
        resource_ref=None,
    )

    student_tasks = service.list_tasks(
        course_id="course-1",
        user_id="student-1",
        include_unpublished=False,
    )
    teacher_tasks = service.list_tasks(
        course_id="course-1",
        user_id="teacher-1",
        include_unpublished=True,
    )

    assert [item.task.task_id for item in student_tasks] == [published.task_id]
    assert student_tasks[0].my_progress is not None
    assert student_tasks[0].my_progress.progress_percent == 10
    assert {item.task.task_id for item in teacher_tasks} == {
        draft.task_id,
        published.task_id,
    }


def test_teacher_summary_includes_not_started_students(service):
    task = _create_task(service)
    service.publish_task(
        course_id="course-1",
        task_id=task.task_id,
        teacher_id="teacher-1",
    )
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )

    summary = service.get_task_summary(
        course_id="course-1",
        task_id=task.task_id,
        teacher_id="teacher-1",
    )

    assert summary.enrolled_students == 2
    assert summary.started_students == 1
    assert summary.completed_students == 1
    assert summary.completion_rate == 0.5
    assert [(item.student_id, item.status) for item in summary.progress] == [
        ("student-1", "completed"),
        ("student-2", "not_started"),
    ]


def test_student_agent_context_never_contains_another_student(service):
    task = _create_task(service)
    service.publish_task(
        course_id="course-1",
        task_id=task.task_id,
        teacher_id="teacher-1",
    )

    context = service.get_student_agent_context(
        course_id="course-1",
        student_id="student-1",
        limit=10,
    )

    assert context["projection"] == "student"
    assert "student-2" not in str(context)
    assert context["pending_tasks"][0]["task_id"] == task.task_id


@pytest.mark.parametrize("event_type", ["resource_completed", "assessment_scored"])
def test_evidence_events_require_an_assigned_resource(service, event_type):
    task = _create_task(service)
    service.publish_task(course_id="course-1", task_id=task.task_id, teacher_id="teacher-1")

    with pytest.raises(LearningRuleError) as error:
        service.record_student_event(
            course_id="course-1",
            task_id=task.task_id,
            student_id="student-1",
            event_id=f"evt-{event_type}",
            event_type=event_type,
            progress_percent=100,
            resource_ref=None,
            evidence=None,
        )

    assert error.value.code == "EVIDENCE_SOURCE_REQUIRED"


def test_assessment_event_requires_evidence(service):
    task = _create_task(
        service,
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
    )
    service.publish_task(course_id="course-1", task_id=task.task_id, teacher_id="teacher-1")

    with pytest.raises(LearningRuleError) as error:
        service.record_student_event(
            course_id="course-1",
            task_id=task.task_id,
            student_id="student-1",
            event_id="evt-score",
            event_type="assessment_scored",
            progress_percent=100,
            resource_ref={"material_type": "report", "material_id": "report-1"},
            evidence=None,
        )

    assert error.value.code == "ASSESSMENT_EVIDENCE_REQUIRED"


def test_assessment_event_persists_evidence(service):
    task = _create_task(
        service,
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
    )
    service.publish_task(course_id="course-1", task_id=task.task_id, teacher_id="teacher-1")

    result = service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-score",
        event_type="assessment_scored",
        progress_percent=100,
        resource_ref={"material_type": "report", "material_id": "report-1"},
        evidence={
            "evidence_type": "score",
            "source_type": "quiz",
            "source_id": "quiz-attempt-1",
            "value": 92.0,
        },
    )

    assert result.progress.completion_basis == "assessment_verified"
    assert result.progress.evidence_count == 1


def test_student_overview_contains_only_own_learning(service):
    completed = _create_task(service)
    pending = _create_task(service)
    for task in (completed, pending):
        service.publish_task(
            course_id="course-1", task_id=task.task_id, teacher_id="teacher-1"
        )
    service.record_student_event(
        course_id="course-1",
        task_id=completed.task_id,
        student_id="student-1",
        event_id="evt-student-overview-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )
    service.record_student_event(
        course_id="course-1",
        task_id=pending.task_id,
        student_id="student-2",
        event_id="evt-other-student-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )

    overview = service.get_learning_overview(
        course_id="course-1", user_id="student-1", actor_role="student"
    )

    assert overview.pending_tasks == 1
    assert overview.self_reported_completed_tasks == 1
    assert "student-2" not in repr(overview)


def test_teacher_overview_reports_completion_bases_without_private_chat(service):
    task = _create_task(
        service,
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
    )
    service.publish_task(
        course_id="course-1", task_id=task.task_id, teacher_id="teacher-1"
    )
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-teacher-overview-evidence",
        event_type="resource_completed",
        progress_percent=100,
        resource_ref={"material_type": "report", "material_id": "report-1"},
    )
    service.record_student_event(
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_id="evt-teacher-overview-complete",
        event_type="completed",
        progress_percent=100,
        resource_ref=None,
    )

    overview = service.get_learning_overview(
        course_id="course-1", user_id="teacher-1", actor_role="teacher"
    )

    assert overview.enrolled_students == 2
    assert overview.activity_evidenced_students == 1
    assert not hasattr(overview, "conversation_history")


def test_student_overview_requires_course_read_membership(service):
    task = _create_task(service)
    service.publish_task(
        course_id="course-1", task_id=task.task_id, teacher_id="teacher-1"
    )

    with pytest.raises(LearningRuleError) as error:
        service.get_learning_overview(
            course_id="course-1", user_id="student-outsider", actor_role="student"
        )

    assert error.value.code == "COURSE_READ_REQUIRED"

