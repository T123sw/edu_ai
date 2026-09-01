from __future__ import annotations

from dataclasses import replace

from app.classroom_catalog.service import ClassroomCatalogService
from app.resource_learning.models import ResourceLearningProgressRecord
from app.standard_resources.service import (
    StandardResourceCatalog,
    StandardResourceLeaf,
    StandardResourceSlot,
)


class _StandardResources:
    def list_course_resources(self, *, course_id: str, can_manage: bool):
        guide = StandardResourceSlot(
            standard_kind="study_guide",
            material_type="report",
            material_id="guide-1",
            review_status="pending" if can_manage else "approved",
            current_version=2 if can_manage else 1,
            approved_version=1,
            resource={
                "title": "待审核指南 v2" if can_manage else "已发布指南 v1",
                "version": 2 if can_manage else 1,
                "rejection_reason": "仅教师可见" if can_manage else None,
            },
        )
        practice = StandardResourceSlot(
            standard_kind="practice",
            material_type="quiz",
            material_id="practice-1",
            review_status="pending",
            current_version=1,
            approved_version=None,
            resource={"title": "待审核习题"},
        )
        slots = [guide, practice] if can_manage else [replace(guide, review_status="approved")]
        return StandardResourceCatalog(
            course_id=course_id,
            leaves=[
                StandardResourceLeaf(
                    leaf_id="leaf-1",
                    title="1.1 线性表",
                    chapter_id="chapter-1",
                    chapter_title="第一章",
                    path_titles=("数据结构", "第一章", "1.1 线性表"),
                    slots=slots,
                )
            ],
        )


class _Learning:
    def list_my_course_progress(self, course_id: str, student_id: str):
        return [
            ResourceLearningProgressRecord(
                course_id=course_id,
                resource_id="guide-1",
                resource_version=1,
                status="completed",
                explanation_covered_ms=0,
                explanation_total_ms=0,
                explanation_coverage_percent=0,
                required_question_count=0,
                answered_question_count=0,
                question_completion_percent=0,
                correct_count_first=0,
                correct_count_latest=0,
                demo_view_count=0,
                demo_interaction_count=0,
                started_at="2026-09-01T00:00:00+00:00",
                completed_at="2026-09-01T00:01:00+00:00",
                last_activity_at="2026-09-01T00:01:00+00:00",
                updated_at="2026-09-01T00:01:00+00:00",
                completion_basis="explicit_read",
            )
        ]


def test_catalog_projection_separates_teacher_review_and_student_progress() -> None:
    service = ClassroomCatalogService(_StandardResources(), _Learning())

    teacher = service.build(course_id="course-1", mode="manage", student_id=None)
    student = service.build(course_id="course-1", mode="learn", student_id="student-1")

    assert teacher["leaves"][0]["summary"] == {"pending": 2, "published": 1}
    assert teacher["leaves"][0]["resources"][0]["current_version"] == 2
    assert teacher["leaves"][0]["resources"][0]["approved_version"] == 1
    assert [item["material_id"] for item in student["leaves"][0]["resources"]] == ["guide-1"]
    assert student["leaves"][0]["learning_summary"] == {"completed": 1, "total": 1}
    assert student["leaves"][0]["resources"][0]["progress"]["completion_basis"] == "explicit_read"
