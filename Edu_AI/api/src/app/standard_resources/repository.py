"""Postgres-backed transactions for standard-resource batches and review."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.database import (
    Material,
    MaterialVersion,
    ResourceLearningManifestModel,
    StandardResourceBatch,
    StandardResourceBatchItem,
    database_session,
)
from app.resource_learning.models import ResourceLearningManifestRecord
from app.persistence.postgres_repositories import _iso_timestamp

from .models import (
    STANDARD_KINDS,
    LeafNode,
    stable_material_id,
    standard_material_type,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StandardResourceRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class StandardResourceRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _item_payload(item: StandardResourceBatchItem) -> dict[str, Any]:
        return {
            "batch_item_id": item.batch_item_id,
            "batch_id": item.batch_id,
            "leaf_id": item.leaf_id,
            "leaf_title": item.leaf_title,
            "standard_kind": item.standard_kind,
            "material_type": item.material_type,
            "material_id": item.material_id,
            "status": item.status,
            "job_id": item.job_id,
            "attempt_count": item.attempt_count,
            "error": dict(item.error or {}) if item.error else None,
            "created_at": _iso_timestamp(item.created_at),
            "updated_at": _iso_timestamp(item.updated_at),
            "finished_at": _iso_timestamp(item.finished_at) if item.finished_at else None,
        }

    @classmethod
    def _batch_payload(
        cls,
        batch: StandardResourceBatch,
        items: Iterable[StandardResourceBatchItem],
    ) -> dict[str, Any]:
        return {
            "batch_id": batch.batch_id,
            "course_id": batch.course_id,
            "created_by": batch.created_by,
            "status": batch.status,
            "total_items": batch.total_items,
            "queued_items": batch.queued_items,
            "running_items": batch.running_items,
            "succeeded_items": batch.succeeded_items,
            "failed_items": batch.failed_items,
            "created_at": _iso_timestamp(batch.created_at),
            "updated_at": _iso_timestamp(batch.updated_at),
            "finished_at": _iso_timestamp(batch.finished_at) if batch.finished_at else None,
            "items": [cls._item_payload(item) for item in items],
        }

    def create_batch(
        self,
        *,
        course_id: str,
        created_by: str,
        leaves: list[LeafNode],
    ) -> dict[str, Any]:
        if not leaves:
            raise StandardResourceRuleError(
                "NO_LEAF_SELECTED", "At least one leaf knowledge point is required"
            )
        batch_id = f"standard-batch-{uuid4().hex}"
        now = _now()
        item_count = len(leaves) * len(STANDARD_KINDS)
        with database_session(engine=self._engine) as session:
            batch = StandardResourceBatch(
                batch_id=batch_id,
                course_id=str(course_id).strip(),
                created_by=str(created_by).strip(),
                status="queued",
                total_items=item_count,
                queued_items=item_count,
                running_items=0,
                succeeded_items=0,
                failed_items=0,
                created_at=now,
                updated_at=now,
            )
            session.add(batch)
            for leaf in leaves:
                for kind in STANDARD_KINDS:
                    session.add(
                        StandardResourceBatchItem(
                            batch_item_id=f"standard-item-{uuid4().hex}",
                            batch_id=batch_id,
                            leaf_id=leaf.leaf_id,
                            leaf_title=leaf.title,
                            standard_kind=kind.value,
                            material_type=standard_material_type(kind),
                            material_id=stable_material_id(leaf.leaf_id, kind),
                            status="queued",
                            attempt_count=0,
                            created_at=now,
                            updated_at=now,
                        )
                    )
        result = self.get_batch(course_id=course_id, batch_id=batch_id)
        if result is None:
            raise RuntimeError("failed to persist standard resource batch")
        return result

    def get_batch(self, *, course_id: str, batch_id: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            batch = session.get(StandardResourceBatch, batch_id)
            if batch is None or batch.course_id != course_id:
                return None
            items = session.scalars(
                select(StandardResourceBatchItem)
                .where(StandardResourceBatchItem.batch_id == batch_id)
                .order_by(
                    StandardResourceBatchItem.leaf_id,
                    StandardResourceBatchItem.standard_kind,
                )
            ).all()
            return self._batch_payload(batch, items)

    def mark_submitted(self, *, batch_item_id: str, job_id: str) -> None:
        now = _now()
        with database_session(engine=self._engine) as session:
            item = session.get(StandardResourceBatchItem, batch_item_id)
            if item is None:
                raise StandardResourceRuleError("BATCH_ITEM_NOT_FOUND", "Batch item was not found")
            item.job_id = str(job_id).strip()
            item.status = "running"
            item.attempt_count += 1
            item.error = None
            item.finished_at = None
            item.updated_at = now
            self._recount(session, item.batch_id, now=now)

    def mark_failed(
        self, *, batch_item_id: str, code: str, message: str
    ) -> None:
        now = _now()
        with database_session(engine=self._engine) as session:
            item = session.get(StandardResourceBatchItem, batch_item_id)
            if item is None:
                raise StandardResourceRuleError("BATCH_ITEM_NOT_FOUND", "Batch item was not found")
            item.status = "failed"
            item.error = {"code": str(code), "message": str(message)}
            item.finished_at = now
            item.updated_at = now
            self._recount(session, item.batch_id, now=now)

    def mark_succeeded(self, *, batch_item_id: str) -> None:
        now = _now()
        with database_session(engine=self._engine) as session:
            item = session.get(StandardResourceBatchItem, batch_item_id)
            if item is None:
                raise StandardResourceRuleError("BATCH_ITEM_NOT_FOUND", "Batch item was not found")
            item.status = "succeeded"
            item.error = None
            item.finished_at = now
            item.updated_at = now
            self._recount(session, item.batch_id, now=now)

    @staticmethod
    def _recount(session, batch_id: str, *, now: datetime) -> None:
        batch = session.get(StandardResourceBatch, batch_id)
        if batch is None:
            return
        items = session.scalars(
            select(StandardResourceBatchItem).where(
                StandardResourceBatchItem.batch_id == batch_id
            )
        ).all()
        counts = {
            status: sum(1 for item in items if item.status == status)
            for status in ("queued", "running", "succeeded", "failed")
        }
        batch.queued_items = counts["queued"]
        batch.running_items = counts["running"]
        batch.succeeded_items = counts["succeeded"]
        batch.failed_items = counts["failed"]
        batch.updated_at = now
        if counts["queued"] or counts["running"]:
            batch.status = "running"
            batch.finished_at = None
        elif counts["failed"] and counts["succeeded"]:
            batch.status = "partial"
            batch.finished_at = now
        elif counts["failed"]:
            batch.status = "failed"
            batch.finished_at = now
        else:
            batch.status = "completed"
            batch.finished_at = now

    def review_material(
        self,
        *,
        course_id: str,
        material_id: str,
        reviewer_id: str,
        decision: str,
        reason: str = "",
    ) -> dict[str, Any]:
        return self.review_material_with_manifest(
            course_id=course_id,
            material_id=material_id,
            reviewer_id=reviewer_id,
            decision=decision,
            reason=reason,
            manifest=None,
        )

    def review_material_with_manifest(
        self,
        *,
        course_id: str,
        material_id: str,
        reviewer_id: str,
        decision: str,
        reason: str = "",
        manifest: ResourceLearningManifestRecord | None,
    ) -> dict[str, Any]:
        normalized_decision = str(decision).strip().lower()
        if normalized_decision not in {"approved", "rejected"}:
            raise StandardResourceRuleError(
                "INVALID_REVIEW_DECISION", "Decision must be approved or rejected"
            )
        if normalized_decision == "rejected" and not str(reason).strip():
            raise StandardResourceRuleError(
                "REJECTION_REASON_REQUIRED", "A rejection reason is required"
            )
        now = _now()
        with database_session(engine=self._engine) as session:
            material = session.scalar(
                select(Material).where(
                    Material.course_id == course_id,
                    Material.material_id == material_id,
                    Material.origin_type == "standard",
                )
            )
            if material is None:
                raise StandardResourceRuleError(
                    "STANDARD_RESOURCE_NOT_FOUND", "Standard resource was not found"
                )
            version = session.scalar(
                select(MaterialVersion).where(
                    MaterialVersion.course_id == material.course_id,
                    MaterialVersion.material_type == material.material_type,
                    MaterialVersion.material_id == material.material_id,
                    MaterialVersion.version == material.version,
                )
            )
            if version is None:
                raise StandardResourceRuleError(
                    "MATERIAL_VERSION_NOT_FOUND", "Current material version was not found"
                )
            if version.review_status != "pending":
                raise StandardResourceRuleError(
                    "VERSION_NOT_PENDING", "Only a pending version can be reviewed"
                )
            if manifest is not None:
                if normalized_decision != "approved":
                    raise StandardResourceRuleError(
                        "LEARNING_MANIFEST_UNEXPECTED",
                        "A learning manifest is only valid for approval",
                    )
                if (
                    manifest.course_id != material.course_id
                    or manifest.resource_id != material.material_id
                    or manifest.resource_version != material.version
                ):
                    raise StandardResourceRuleError(
                        "LEARNING_MANIFEST_MISMATCH",
                        "Learning manifest does not match the reviewed version",
                    )
                existing_manifest = session.scalar(
                    select(ResourceLearningManifestModel).where(
                        ResourceLearningManifestModel.course_id == manifest.course_id,
                        ResourceLearningManifestModel.resource_id == manifest.resource_id,
                        ResourceLearningManifestModel.resource_version == manifest.resource_version,
                    )
                )
                if existing_manifest is None:
                    session.add(
                        ResourceLearningManifestModel(
                            manifest_id=manifest.manifest_id,
                            course_id=manifest.course_id,
                            resource_id=manifest.resource_id,
                            resource_version=manifest.resource_version,
                            content_hash=manifest.content_hash,
                            mode=manifest.mode,
                            manifest_json={
                                "scenes": [asdict(item) for item in manifest.scenes],
                                "questions": [asdict(item) for item in manifest.questions],
                            },
                            created_at=datetime.fromisoformat(
                                manifest.created_at.replace("Z", "+00:00")
                            ),
                        )
                    )
                elif existing_manifest.content_hash != manifest.content_hash:
                    raise StandardResourceRuleError(
                        "LEARNING_MANIFEST_IMMUTABLE",
                        "Published learning manifest is immutable",
                    )
            version.review_status = normalized_decision
            version.reviewed_by = reviewer_id
            version.reviewed_at = now
            version.rejection_reason = str(reason).strip() or None
            material.current_review_status = normalized_decision
            if normalized_decision == "approved":
                material.approved_version = material.version
                material.approved_by = reviewer_id
                material.approved_at = now
            raw_payload = dict(material.raw_payload or {})
            raw_payload.update(
                {
                    "current_review_status": material.current_review_status,
                    "approved_version": material.approved_version,
                    "approved_by": material.approved_by,
                    "approved_at": (
                        _iso_timestamp(material.approved_at)
                        if material.approved_at
                        else None
                    ),
                }
            )
            material.raw_payload = raw_payload
            result = {
                "course_id": material.course_id,
                "material_type": material.material_type,
                "material_id": material.material_id,
                "version": material.version,
                "current_review_status": material.current_review_status,
                "approved_version": material.approved_version,
                "approved_by": material.approved_by,
                "approved_at": (
                    _iso_timestamp(material.approved_at)
                    if material.approved_at
                    else None
                ),
            }
        return result

    def list_pending_material_ids_in_batch(
        self, *, course_id: str, batch_id: str
    ) -> list[str]:
        with database_session(engine=self._engine) as session:
            return list(
                session.scalars(
                    select(Material.material_id).where(
                        Material.course_id == course_id,
                        Material.generation_batch_id == batch_id,
                        Material.origin_type == "standard",
                        Material.current_review_status == "pending",
                    )
                ).all()
            )

    def approve_pending_in_batch(
        self, *, course_id: str, batch_id: str, reviewer_id: str
    ) -> list[dict[str, Any]]:
        material_ids = self.list_pending_material_ids_in_batch(
            course_id=course_id, batch_id=batch_id
        )
        return [
            self.review_material(
                course_id=course_id,
                material_id=material_id,
                reviewer_id=reviewer_id,
                decision="approved",
            )
            for material_id in material_ids
        ]
