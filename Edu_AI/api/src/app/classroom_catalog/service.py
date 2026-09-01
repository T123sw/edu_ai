from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from app.resource_learning.models import ResourceLearningProgressRecord
from app.resource_learning.service import ResourceLearningService
from app.standard_resources.service import StandardResourceService


CatalogMode = Literal["manage", "learn"]


def _compact_progress(
    progress: ResourceLearningProgressRecord | None,
) -> dict | None:
    if progress is None:
        return None
    return {
        "resource_id": progress.resource_id,
        "resource_version": progress.resource_version,
        "status": progress.status,
        "completion_basis": progress.completion_basis,
        "explanation_coverage_percent": progress.explanation_coverage_percent,
        "answered_question_count": progress.answered_question_count,
        "required_question_count": progress.required_question_count,
        "completed_at": progress.completed_at,
        "last_activity_at": progress.last_activity_at,
    }


class ClassroomCatalogService:
    def __init__(
        self,
        standard_resources: StandardResourceService,
        resource_learning: ResourceLearningService,
    ):
        self.standard_resources = standard_resources
        self.resource_learning = resource_learning

    def build(
        self,
        *,
        course_id: str,
        mode: CatalogMode,
        student_id: str | None,
    ) -> dict:
        can_manage = mode == "manage"
        catalog = self.standard_resources.list_course_resources(
            course_id=course_id,
            can_manage=can_manage,
        )
        progress_by_resource: dict[
            tuple[str, int], ResourceLearningProgressRecord
        ] = {}
        if mode == "learn" and student_id:
            progress_by_resource = {
                (item.resource_id, item.resource_version): item
                for item in self.resource_learning.list_my_course_progress(
                    course_id, student_id
                )
            }

        leaves: list[dict] = []
        for leaf in catalog.leaves:
            resources: list[dict] = []
            for slot in leaf.slots:
                if mode == "learn" and slot.approved_version is None:
                    continue
                payload = asdict(slot)
                version = slot.approved_version if mode == "learn" else slot.current_version
                payload["progress"] = (
                    _compact_progress(
                        progress_by_resource.get((slot.material_id, int(version)))
                    )
                    if mode == "learn" and version is not None
                    else None
                )
                resources.append(payload)

            leaf_payload = {
                "leaf_id": leaf.leaf_id,
                "title": leaf.title,
                "chapter_id": leaf.chapter_id,
                "chapter_title": leaf.chapter_title,
                "path_titles": list(leaf.path_titles),
                "resources": resources,
            }
            if mode == "manage":
                leaf_payload["summary"] = {
                    "pending": sum(
                        1 for slot in leaf.slots if slot.review_status == "pending"
                    ),
                    "published": sum(
                        1 for slot in leaf.slots if slot.approved_version is not None
                    ),
                }
            else:
                leaf_payload["learning_summary"] = {
                    "completed": sum(
                        1
                        for item in resources
                        if item.get("progress")
                        and item["progress"].get("status") == "completed"
                    ),
                    "total": len(resources),
                }
            leaves.append(leaf_payload)

        return {"course_id": course_id, "mode": mode, "leaves": leaves}
