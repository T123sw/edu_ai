from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .models import ResourceLearningManifestRecord, ResourceLearningProgressRecord


QUEUE_KEYS = (
    "not_started",
    "coverage_pending",
    "coverage_ready_questions_pending",
    "questions_ready_coverage_pending",
    "completed",
)


def _ratio(numerator: int, denominator: int) -> dict[str, int | float]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": round(numerator * 100 / denominator, 2) if denominator else 0.0,
    }


def build_resource_learning_analytics(
    *,
    manifest: ResourceLearningManifestRecord,
    progress_records: Sequence[tuple[str, ResourceLearningProgressRecord]],
    question_attempts: Sequence[Mapping[str, Any]],
    enrolled_student_ids: Sequence[str],
) -> dict[str, Any]:
    enrolled = tuple(dict.fromkeys(str(item) for item in enrolled_student_ids if str(item)))
    progress_by_student = {student_id: progress for student_id, progress in progress_records}
    denominator = len(enrolled)
    completed = sum(
        progress_by_student.get(student_id) is not None
        and progress_by_student[student_id].status == "completed"
        for student_id in enrolled
    )
    started = sum(
        progress_by_student.get(student_id) is not None
        and progress_by_student[student_id].status != "not_started"
        for student_id in enrolled
    )
    all_answered = sum(
        progress_by_student.get(student_id) is not None
        and progress_by_student[student_id].answered_question_count
        == progress_by_student[student_id].required_question_count
        for student_id in enrolled
    )
    demo_view_students = sum(
        progress_by_student.get(student_id) is not None
        and progress_by_student[student_id].demo_view_count > 0
        for student_id in enrolled
    )
    demo_interaction_students = sum(
        progress_by_student.get(student_id) is not None
        and progress_by_student[student_id].demo_interaction_count > 0
        for student_id in enrolled
    )

    queues = {key: 0 for key in QUEUE_KEYS}
    for student_id in enrolled:
        progress = progress_by_student.get(student_id)
        if progress is None or progress.status == "not_started":
            queues["not_started"] += 1
        elif progress.status == "completed":
            queues["completed"] += 1
        else:
            coverage_ready = progress.explanation_coverage_percent >= 80.0
            questions_ready = (
                progress.answered_question_count == progress.required_question_count
            )
            if coverage_ready and not questions_ready:
                queues["coverage_ready_questions_pending"] += 1
            elif questions_ready and not coverage_ready:
                queues["questions_ready_coverage_pending"] += 1
            else:
                queues["coverage_pending"] += 1

    attempts_by_question_student: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    knowledge_errors: dict[str, dict[str, Any]] = {}
    for attempt in question_attempts:
        student_id = str(attempt["student_id"])
        question_id = str(attempt["question_id"])
        attempts_by_question_student[(question_id, student_id)].append(attempt)
        if not bool(attempt.get("is_correct")):
            for raw_knowledge_id in attempt.get("knowledge_point_ids") or ():
                knowledge_id = str(raw_knowledge_id)
                item = knowledge_errors.setdefault(
                    knowledge_id,
                    {"knowledge_point_id": knowledge_id, "incorrect_attempt_count": 0, "student_ids": set()},
                )
                item["incorrect_attempt_count"] += 1
                item["student_ids"].add(student_id)

    question_analytics = []
    for question in manifest.questions:
        student_attempts = {
            student_id: sorted(values, key=lambda item: int(item["attempt_number"]))
            for (question_id, student_id), values in attempts_by_question_student.items()
            if question_id == question.question_id and student_id in enrolled
        }
        answered_count = len(student_attempts)
        first_correct = sum(bool(values[0].get("is_correct")) for values in student_attempts.values())
        latest_correct = sum(bool(values[-1].get("is_correct")) for values in student_attempts.values())
        option_counts: dict[str, int] = defaultdict(int)
        for values in student_attempts.values():
            for value in values[-1].get("values") or ():
                option_counts[str(value)] += 1
        question_analytics.append(
            {
                "question_id": question.question_id,
                "response_rate": _ratio(answered_count, denominator),
                "first_correct_rate": _ratio(first_correct, answered_count),
                "latest_correct_rate": _ratio(latest_correct, answered_count),
                "option_distribution": [
                    {"value": value, "count": count}
                    for value, count in sorted(option_counts.items())
                ],
            }
        )

    tracked = [progress_by_student[item] for item in enrolled if item in progress_by_student]
    knowledge_point_errors = [
        {
            "knowledge_point_id": item["knowledge_point_id"],
            "incorrect_student_count": len(item["student_ids"]),
            "incorrect_attempt_count": item["incorrect_attempt_count"],
        }
        for item in sorted(knowledge_errors.values(), key=lambda value: value["knowledge_point_id"])
    ]
    return {
        "course_id": manifest.course_id,
        "resource_id": manifest.resource_id,
        "resource_version": manifest.resource_version,
        "enrolled_student_count": denominator,
        "tracked_student_count": len(tracked),
        "started_student_count": started,
        "completed_student_count": completed,
        "in_progress_student_count": sum(item.status == "in_progress" for item in tracked),
        "not_started_student_count": queues["not_started"],
        "completion_rate": round(completed / denominator, 4) if denominator else 0.0,
        "completion_rate_ratio": _ratio(completed, denominator),
        "average_explanation_coverage_percent": round(
            sum(item.explanation_coverage_percent for item in tracked) / denominator, 2
        ) if denominator else 0.0,
        "average_question_completion_percent": round(
            sum(item.question_completion_percent for item in tracked) / denominator, 2
        ) if denominator else 0.0,
        "all_questions_answered_student_count": all_answered,
        "demo_view_student_count": demo_view_students,
        "demo_interaction_student_count": demo_interaction_students,
        "demo_view_count": sum(item.demo_view_count for item in tracked),
        "demo_interaction_count": sum(item.demo_interaction_count for item in tracked),
        "queues": queues,
        "question_analytics": question_analytics,
        "knowledge_point_errors": knowledge_point_errors,
    }
