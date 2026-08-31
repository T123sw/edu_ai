from app.resource_learning.analytics import build_resource_learning_analytics
from app.resource_learning.models import (
    ManifestQuestion,
    ManifestScene,
    ResourceLearningManifestRecord,
    ResourceLearningProgressRecord,
)


def _progress(student_status, coverage, answered, *, demos=0):
    return ResourceLearningProgressRecord(
        course_id="course-1", resource_id="classroom-1", resource_version=3,
        status=student_status, explanation_covered_ms=coverage * 10,
        explanation_total_ms=1000, explanation_coverage_percent=float(coverage),
        required_question_count=2, answered_question_count=answered,
        question_completion_percent=answered * 50.0, correct_count_first=0,
        correct_count_latest=0, demo_view_count=demos, demo_interaction_count=0,
        started_at="2026-08-31T00:00:00+00:00", completed_at=None,
        last_activity_at="2026-08-31T00:00:00+00:00", updated_at="2026-08-31T00:00:00+00:00",
    )


def test_analytics_uses_enrollment_denominator_and_separate_queues():
    manifest = ResourceLearningManifestRecord(
        manifest_id="m1", course_id="course-1", resource_id="classroom-1",
        resource_version=3, content_hash="hash", mode="completable",
        scenes=(ManifestScene("s1", "explanation", 1000, (), ()),),
        questions=(
            ManifestQuestion("q1", "quiz", "single", True, ("A",), ("kp1",)),
            ManifestQuestion("q2", "quiz", "single", True, ("B",), ("kp2",)),
        ), created_at="2026-08-31T00:00:00+00:00",
    )
    records = [
        ("s1", _progress("completed", 100, 2, demos=1)),
        ("s2", _progress("in_progress", 85, 1, demos=1)),
        ("s3", _progress("in_progress", 35, 2)),
    ]
    attempts = [
        {"student_id": "s1", "question_id": "q1", "attempt_number": 1, "values": ["A"], "is_correct": True, "knowledge_point_ids": ["kp1"]},
        {"student_id": "s2", "question_id": "q1", "attempt_number": 1, "values": ["B"], "is_correct": False, "knowledge_point_ids": ["kp1"]},
    ]

    result = build_resource_learning_analytics(
        manifest=manifest,
        progress_records=records,
        question_attempts=attempts,
        enrolled_student_ids=["s1", "s2", "s3", "s4"],
    )

    assert result["enrolled_student_count"] == 4
    assert result["completed_student_count"] == 1
    assert result["completion_rate"] == 0.25
    assert result["queues"]["coverage_ready_questions_pending"] == 1
    assert result["queues"]["questions_ready_coverage_pending"] == 1
    assert result["queues"]["not_started"] == 1
    assert result["question_analytics"][0]["response_rate"] == {
        "numerator": 2, "denominator": 4, "percent": 50.0
    }
    assert result["knowledge_point_errors"][0]["knowledge_point_id"] == "kp1"
