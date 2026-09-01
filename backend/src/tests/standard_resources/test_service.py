from __future__ import annotations

from app.standard_resources.service import StandardResourceService

from .test_models import GRAPH


def _material(*, approved_version: int | None, current_version: int = 2) -> dict:
    return {
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "standard-relationships-and-keys-study_guide",
        "title": "关系与键学习指南",
        "origin_type": "standard",
        "standard_kind": "study_guide",
        "scope_type": "knowledge_point",
        "scope_id": "relationships-and-keys",
        "version": current_version,
        "approved_version": approved_version,
        "current_review_status": "pending",
        "content": "new pending content",
    }


def test_teacher_listing_contains_every_leaf_and_three_slots() -> None:
    service = StandardResourceService(
        graph_lookup=lambda _course_id: GRAPH,
        material_list=lambda _course_id: [_material(approved_version=1)],
        version_lookup=lambda *_args: {"version": 1, "content": "approved content"},
    )

    result = service.list_course_resources(course_id="course-1", can_manage=True)

    assert len(result.leaves) == 4
    assert [slot.standard_kind for slot in result.leaves[0].slots] == [
        "classroom",
        "study_guide",
        "practice",
    ]
    guide = result.leaves[0].slots[1]
    assert guide.current_version == 2
    assert guide.approved_version == 1
    assert guide.review_status == "pending"
    assert guide.resource["content"] == "new pending content"


def test_student_listing_exposes_only_the_approved_version() -> None:
    service = StandardResourceService(
        graph_lookup=lambda _course_id: GRAPH,
        material_list=lambda _course_id: [_material(approved_version=1)],
        version_lookup=lambda *_args: {"version": 1, "content": "approved content"},
    )

    result = service.list_course_resources(course_id="course-1", can_manage=False)

    first_leaf = result.leaves[0]
    assert [slot.standard_kind for slot in first_leaf.slots] == ["study_guide"]
    assert first_leaf.slots[0].resource["content"] == "approved content"
    assert first_leaf.slots[0].current_version == 1
    assert result.leaves[1].slots == []


def test_student_listing_hides_pending_resource_without_approved_version() -> None:
    service = StandardResourceService(
        graph_lookup=lambda _course_id: GRAPH,
        material_list=lambda _course_id: [_material(approved_version=None)],
        version_lookup=lambda *_args: None,
    )

    result = service.list_course_resources(course_id="course-1", can_manage=False)

    assert all(leaf.slots == [] for leaf in result.leaves)
