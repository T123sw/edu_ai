from __future__ import annotations

from dataclasses import replace

import pytest

from app.assessment.models import AssessmentAttemptRecord, AssessmentItemRecord
from app.assessment.policies import (
    AssessmentPolicyError,
    can_reveal_answers,
    grade_objective_item,
    select_best_attempt,
    validate_settings,
)


def _item(*, item_type: str, scoring_key: dict, max_score: float = 10) -> AssessmentItemRecord:
    return AssessmentItemRecord.new(
        assessment_version_id="asv-1",
        position=1,
        item_type=item_type,
        prompt={"stem": "题目", "options": [{"id": "a", "text": "A"}]},
        scoring_key=scoring_key,
        rubric={},
        max_score=max_score,
        grading_provider=(
            "rubric_ai_teacher"
            if item_type in {"short_answer", "artifact", "code_implementation"}
            else "deterministic"
        ),
        knowledge_point_ids=["loops"],
        source_refs=[{"material_type": "report", "material_id": "report-1"}],
        created_origin="teacher",
    )


def _attempt(*, attempt_number: int, final_score: float | None, status: str = "graded") -> AssessmentAttemptRecord:
    record = AssessmentAttemptRecord.new(
        assignment_id="asa-1",
        assessment_version_id="asv-1",
        task_id="lt-1",
        course_id="course-1",
        student_id="student-1",
        attempt_number=attempt_number,
    )
    return replace(record, status=status, final_score=final_score)


def test_settings_reject_mastery_below_pass_threshold():
    with pytest.raises(AssessmentPolicyError) as error:
        validate_settings(pass_threshold=80, mastery_threshold=60, max_attempts=3)

    assert error.value.code == "INVALID_ASSESSMENT_SETTINGS"


@pytest.mark.parametrize("max_attempts", [0, 11])
def test_settings_reject_attempt_limits_outside_one_to_ten(max_attempts: int):
    with pytest.raises(AssessmentPolicyError) as error:
        validate_settings(
            pass_threshold=60,
            mastery_threshold=80,
            max_attempts=max_attempts,
        )

    assert error.value.code == "INVALID_ASSESSMENT_SETTINGS"


def test_multiple_choice_grading_uses_stable_option_ids_not_order():
    item = _item(
        item_type="multiple_choice",
        scoring_key={"correct_option_ids": ["a", "c"]},
    )

    grade = grade_objective_item(item, {"selected_option_ids": ["c", "a"]})

    assert grade.status == "graded"
    assert grade.final_score == 10
    assert grade.correct is True


def test_structured_blank_grading_normalizes_case_and_whitespace():
    item = _item(
        item_type="structured_blank",
        scoring_key={"accepted_answers": ["While Loop"]},
    )

    grade = grade_objective_item(item, {"text": "  while loop  "})

    assert grade.final_score == 10
    assert grade.correct is True


def test_subjective_answer_stays_pending_teacher_review():
    item = _item(item_type="short_answer", scoring_key={})

    grade = grade_objective_item(item, {"text": "用不变量解释循环。"})

    assert grade.status == "pending_review"
    assert grade.final_score is None
    assert grade.correct is None


def test_best_attempt_ignores_ungraded_attempts_and_keeps_earliest_tie():
    attempts = [
        _attempt(attempt_number=1, final_score=50),
        _attempt(attempt_number=2, final_score=75),
        _attempt(attempt_number=3, final_score=75),
        _attempt(attempt_number=4, final_score=None, status="pending_review"),
    ]

    best = select_best_attempt(attempts)

    assert best is not None
    assert best.attempt_number == 2
    assert best.final_score == 75


def test_answers_can_only_be_revealed_after_pass_or_attempts_exhausted():
    assert can_reveal_answers(
        result="passed",
        attempts_used=2,
        max_attempts=3,
        reveal_policy="after_finish_or_exhausted",
    ) is True
    assert can_reveal_answers(
        result="not_passed",
        attempts_used=2,
        max_attempts=3,
        reveal_policy="after_finish_or_exhausted",
    ) is False
    assert can_reveal_answers(
        result="not_passed",
        attempts_used=3,
        max_attempts=3,
        reveal_policy="after_finish_or_exhausted",
    ) is True
