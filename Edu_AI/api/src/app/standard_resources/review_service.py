"""Coordinate standard-resource review with immutable learning manifests."""

from __future__ import annotations

from collections.abc import Mapping

from app.resource_learning.manifest import build_classroom_learning_manifest

from .repository import StandardResourceRepository, StandardResourceRuleError


class StandardResourceReviewService:
    def __init__(self, *, repository: StandardResourceRepository, material_repository):
        self.repository = repository
        self.material_repository = material_repository

    def review(
        self,
        *,
        course_id: str,
        material_id: str,
        reviewer_id: str,
        decision: str,
        reason: str = "",
    ) -> dict:
        material = next(
            (
                item
                for item in self.material_repository.list(course_id)
                if str(item.get("material_id") or "") == material_id
                and str(item.get("origin_type") or "") == "standard"
            ),
            None,
        )
        if material is None:
            raise StandardResourceRuleError(
                "STANDARD_RESOURCE_NOT_FOUND", "Standard resource was not found"
            )

        manifest = None
        if str(decision).strip().lower() == "approved" and material.get("standard_kind") == "classroom":
            version_number = int(material.get("version") or 0)
            version = self.material_repository.get_version(
                course_id,
                str(material.get("material_type") or "classroom"),
                material_id,
                version_number,
            )
            if version is None:
                raise StandardResourceRuleError(
                    "MATERIAL_VERSION_NOT_FOUND", "Current material version was not found"
                )
            manifest_payload = dict(version)
            content = version.get("content")
            if not manifest_payload.get("scenes") and isinstance(content, Mapping):
                manifest_payload["scenes"] = content.get("scenes") or []
            manifest_payload.update(
                {
                    "course_id": course_id,
                    "material_id": material_id,
                    "version": version_number,
                }
            )
            try:
                manifest = build_classroom_learning_manifest(manifest_payload)
                if not manifest.scenes or manifest.explanation_total_ms <= 0:
                    raise ValueError("classroom has no measurable explanation scene")
            except (TypeError, ValueError) as error:
                raise StandardResourceRuleError(
                    "LEARNING_MANIFEST_INVALID",
                    "AI classroom cannot be approved because its learning structure is invalid",
                ) from error

        return self.repository.review_material_with_manifest(
            course_id=course_id,
            material_id=material_id,
            reviewer_id=reviewer_id,
            decision=decision,
            reason=reason,
            manifest=manifest,
        )

    def approve_pending_in_batch(
        self, *, course_id: str, batch_id: str, reviewer_id: str
    ) -> list[dict]:
        return [
            self.review(
                course_id=course_id,
                material_id=material_id,
                reviewer_id=reviewer_id,
                decision="approved",
            )
            for material_id in self.repository.list_pending_material_ids_in_batch(
                course_id=course_id, batch_id=batch_id
            )
        ]
