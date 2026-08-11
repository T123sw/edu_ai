from __future__ import annotations

from dataclasses import replace

import pytest

from app.assessment.models import AssessmentItemRecord, AssessmentRecord, AssessmentVersionRecord
from app.assessment.service import AssessmentRuleError, AssessmentService
from app.assessment.store import AssessmentStore
from app.learning.models import LearningTaskRecord
from app.learning.service import LearningService
from app.learning.store import LearningStore


def _service(tmp_path, *, subjective: bool = False):
    memberships = [
        {"user_id": "teacher-1", "role": "owner"},
        {"user_id": "student-1", "role": "viewer"},
    ]
    learning = LearningService(
        store=LearningStore(tmp_path / "learning.db"),
        material_lookup=lambda *_args: None,
        membership_lookup=lambda _course_id: memberships,
    )
    task = LearningTaskRecord.new(
        course_id="course-1",
        title="Loop assessment",
        instructions="Complete the assessment",
        created_by="teacher-1",
        resource_refs=[],
        knowledge_point_ids=["loops"],
    )
    learning.store.create_task(task)
    learning.store.publish_task(task.task_id, course_id="course-1", published_by="teacher-1")
    store = AssessmentStore(tmp_path / "assessment.db")
    assessment = AssessmentRecord("asmt-1", "course-1", task.task_id, "teacher-1")
    version = AssessmentVersionRecord(
        assessment_version_id="asv-1",
        assessment_id="asmt-1",
        version_number=1,
        status="draft",
        source_mode="manual",
        assessment_mode="closed_book",
        pass_threshold=60,
        mastery_threshold=80,
        max_attempts=3,
        score_policy="best_final_score",
        answer_reveal_policy="after_finish_or_exhausted",
        shuffle_questions=False,
        shuffle_options=False,
    )
    store.create_draft(assessment, version)
    items = [
        replace(
            AssessmentItemRecord.new(
                assessment_version_id="asv-1",
                position=index,
                item_type="structured_blank",
                prompt={"stem": f"Answer {index}"},
                scoring_key={"accepted_answers": [f"correct-{index}"]},
                rubric={},
                max_score=25,
                grading_provider="deterministic",
                knowledge_point_ids=["loops"],
                source_refs=[{"material_type": "fixture", "material_id": "source-1"}],
                created_origin="manual",
            ),
            assessment_item_id=f"asi-{index}",
        )
        for index in range(1, 5)
    ]
    if subjective:
        items[-1] = replace(
            items[-1],
            item_type="short_answer",
            scoring_key={},
            rubric={"criteria": ["Clear explanation"]},
            grading_provider="rubric_ai_teacher",
        )
    store.replace_draft_items("asv-1", items, expected_revision=0)
    store.publish_version("asv-1", published_by="teacher-1")
    return AssessmentService(
        store=store,
        learning_service=learning,
        material_lookup=lambda *_args: None,
    ), task


def _answers(correct_count: int):
    return {
        f"asi-{index}": {"text": f"correct-{index}" if index <= correct_count else "wrong"}
        for index in range(1, 5)
    }


def test_three_attempts_keep_best_score_and_history(tmp_path):
    service, task = _service(tmp_path)

    for number, correct_count in enumerate((2, 3, 2), start=1):
        attempt = service.start_attempt(
            course_id="course-1", task_id=task.task_id, student_id="student-1"
        )
        saved = service.save_answers(
            attempt_id=attempt.attempt_id,
            student_id="student-1",
            answers=_answers(correct_count),
            expected_revision=0,
        )
        assert saved.draft_revision == 1
        submitted = service.submit_attempt(
            attempt_id=attempt.attempt_id,
            student_id="student-1",
            idempotency_key=f"submit-{number}",
        )
        assert submitted.final_score == (50, 75, 50)[number - 1]
        assert submitted.submission_idempotency_key == f"submit-{number}"
        assert service.submit_attempt(
            attempt_id=attempt.attempt_id,
            student_id="student-1",
            idempotency_key=f"submit-{number}",
        ) == submitted

    assignment = service.get_student_assignment(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    assert assignment.attempts_used == 3
    assert assignment.best_final_score == 75
    assert assignment.result == "passed"
    assert [item.final_score for item in service.list_student_attempts(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )] == [50, 75, 50]
    with pytest.raises(AssessmentRuleError, match="attempts") as exhausted:
        service.start_attempt(
            course_id="course-1", task_id=task.task_id, student_id="student-1"
        )
    assert exhausted.value.code == "ATTEMPTS_EXHAUSTED"


def test_answer_autosave_rejects_stale_revision(tmp_path):
    service, task = _service(tmp_path)
    attempt = service.start_attempt(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    service.save_answers(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        answers=_answers(1),
        expected_revision=0,
    )

    with pytest.raises(AssessmentRuleError) as conflict:
        service.save_answers(
            attempt_id=attempt.attempt_id,
            student_id="student-1",
            answers=_answers(2),
            expected_revision=0,
        )

    assert conflict.value.code == "ATTEMPT_REVISION_CONFLICT"


def test_subjective_submission_waits_for_teacher_review(tmp_path):
    service, task = _service(tmp_path, subjective=True)
    attempt = service.start_attempt(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    service.save_answers(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        answers=_answers(4),
        expected_revision=0,
    )

    submitted = service.submit_attempt(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        idempotency_key="submit-subjective",
    )

    assert submitted.status == "pending_review"
    assert submitted.final_score is None
    assignment = service.get_student_assignment(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    assert assignment.attempts_used == 1
    assert assignment.result == "pending_review"
