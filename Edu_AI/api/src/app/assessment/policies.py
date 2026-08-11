"""Pure validation, grading, and attempt-selection rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import AssessmentAttemptRecord, AssessmentItemRecord


class AssessmentPolicyError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AssessmentSettings:
    pass_threshold: float
    mastery_threshold: float
    max_attempts: int


@dataclass(frozen=True)
class ItemGrade:
    status: str
    final_score: float | None
    correct: bool | None


def validate_settings(
    pass_threshold: float,
    mastery_threshold: float,
    max_attempts: int,
) -> AssessmentSettings:
    passed = float(pass_threshold)
    mastery = float(mastery_threshold)
    attempts = int(max_attempts)
    if not 0 <= passed <= 100 or not 0 <= mastery <= 100:
        raise AssessmentPolicyError(
            "INVALID_ASSESSMENT_SETTINGS", "Score thresholds must be between 0 and 100"
        )
    if mastery < passed:
        raise AssessmentPolicyError(
            "INVALID_ASSESSMENT_SETTINGS", "Mastery threshold cannot be below pass threshold"
        )
    if not 1 <= attempts <= 10:
        raise AssessmentPolicyError(
            "INVALID_ASSESSMENT_SETTINGS", "Maximum attempts must be between 1 and 10"
        )
    return AssessmentSettings(passed, mastery, attempts)


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def grade_objective_item(
    item: AssessmentItemRecord,
    answer: dict[str, Any],
) -> ItemGrade:
    if item.grading_provider != "deterministic":
        return ItemGrade(status="pending_review", final_score=None, correct=None)

    correct = False
    if item.item_type == "multiple_choice":
        expected = {
            str(value) for value in item.scoring_key.get("correct_option_ids", [])
        }
        supplied = {
            str(value) for value in answer.get("selected_option_ids", [])
        }
        correct = bool(expected) and supplied == expected
    elif item.item_type == "single_choice":
        correct = str(answer.get("selected_option_id", "")) == str(
            item.scoring_key.get("correct_option_id", "")
        )
    elif item.item_type == "judge":
        correct = bool(answer.get("value")) is bool(item.scoring_key.get("correct_value"))
    elif item.item_type in {
        "structured_blank",
        "code_output",
        "code_trace",
        "debug_fix",
    }:
        accepted = {
            _normalized_text(value)
            for value in item.scoring_key.get("accepted_answers", [])
            if _normalized_text(value)
        }
        correct = bool(accepted) and _normalized_text(answer.get("text")) in accepted

    return ItemGrade(
        status="graded",
        final_score=item.max_score if correct else 0.0,
        correct=correct,
    )


def select_best_attempt(
    attempts: Iterable[AssessmentAttemptRecord],
) -> AssessmentAttemptRecord | None:
    candidates = [
        item
        for item in attempts
        if item.status == "graded"
        and item.final_score is not None
        and item.invalidated_at is None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (-float(item.final_score or 0), item.attempt_number))


def can_reveal_answers(
    *,
    result: str,
    attempts_used: int,
    max_attempts: int,
    reveal_policy: str,
) -> bool:
    if reveal_policy == "never":
        return False
    exhausted = int(attempts_used) >= int(max_attempts)
    if reveal_policy == "after_exhausted":
        return exhausted
    if reveal_policy == "after_finish_or_exhausted":
        return result in {"passed", "mastery"} or exhausted
    raise AssessmentPolicyError(
        "INVALID_ASSESSMENT_SETTINGS", "Unknown answer reveal policy"
    )
