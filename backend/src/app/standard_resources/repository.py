"""Postgres-backed transactions for standard-resource batches and review."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

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
            "action": item.action,
            "base_version": item.base_version,
            "material_version": item.material_version,
            "content_hash": item.content_hash,
            "generation_context": dict(item.generation_context or {}),
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
            "idempotency_key": batch.idempotency_key,
            "graph_version": batch.graph_version,
            "generation_mode": batch.generation_mode,
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
        planned_items: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
        graph_version: str = "legacy",
        generation_mode: str = "regenerate_all",
    ) -> dict[str, Any]:
        if not leaves:
            raise StandardResourceRuleError(
                "NO_LEAF_SELECTED", "At least one leaf knowledge point is required"
            )
        normalized_key = str(idempotency_key or "").strip()
        if normalized_key:
            existing = self.find_batch_by_idempotency(
                course_id=course_id, idempotency_key=normalized_key
            )
            if existing is not None:
                return {**existing, "_was_created": False}
        batch_id = f"standard-batch-{uuid4().hex}"
        normalized_key = normalized_key or batch_id
        now = _now()
        specs = list(planned_items or [])
        if not specs:
            specs = [
                {
                    "leaf_id": leaf.leaf_id,
                    "leaf_title": leaf.title,
                    "standard_kind": kind.value,
                    "material_type": standard_material_type(kind),
                    "material_id": stable_material_id(leaf.leaf_id, kind),
                    "action": "generate",
                    "base_version": None,
                    "generation_context": {"path_titles": list(leaf.path_titles)},
                }
                for leaf in leaves
                for kind in STANDARD_KINDS
            ]
        item_count = len(specs)
        try:
            with database_session(engine=self._engine) as session:
                batch = StandardResourceBatch(
                    batch_id=batch_id,
                    course_id=str(course_id).strip(),
                    created_by=str(created_by).strip(),
                    idempotency_key=normalized_key,
                    graph_version=str(graph_version or "legacy"),
                    generation_mode=str(generation_mode or "regenerate_all"),
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
                for spec in specs:
                    leaf_id = str(spec["leaf_id"])
                    kind = str(spec["standard_kind"])
                    session.add(
                        StandardResourceBatchItem(
                            batch_item_id=f"standard-item-{uuid4().hex}",
                            batch_id=batch_id,
                            leaf_id=leaf_id,
                            leaf_title=str(spec["leaf_title"]),
                            standard_kind=kind,
                            material_type=str(spec["material_type"]),
                            material_id=str(spec["material_id"]),
                            action=str(spec.get("action") or "generate"),
                            base_version=spec.get("base_version"),
                            active_slot_key=f"{course_id}:{leaf_id}:{kind}",
                            generation_context=dict(spec.get("generation_context") or {}),
                            status="queued",
                            attempt_count=0,
                            created_at=now,
                            updated_at=now,
                        )
                    )
        except IntegrityError as exc:
            duplicate = self.find_batch_by_idempotency(
                course_id=course_id, idempotency_key=normalized_key
            )
            if duplicate is not None:
                return {**duplicate, "_was_created": False}
            raise StandardResourceRuleError(
                "SLOT_GENERATION_ACTIVE",
                "A selected knowledge resource is already being generated",
            ) from exc
        result = self.get_batch(course_id=course_id, batch_id=batch_id)
        if result is None:
            raise RuntimeError("failed to persist standard resource batch")
        return {**result, "_was_created": True}

    def find_batch_by_idempotency(
        self, *, course_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        normalized_key = str(idempotency_key or "").strip()
        if not normalized_key:
            return None
        with database_session(engine=self._engine) as session:
            batch_id = session.scalar(
                select(StandardResourceBatch.batch_id).where(
                    StandardResourceBatch.course_id == str(course_id).strip(),
                    StandardResourceBatch.idempotency_key == normalized_key,
                )
            )
        if not batch_id:
            return None
        return self.get_batch(course_id=course_id, batch_id=str(batch_id))

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

    def list_batches(self, *, course_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            batches = session.scalars(
                select(StandardResourceBatch)
                .where(StandardResourceBatch.course_id == course_id)
                .order_by(StandardResourceBatch.created_at.desc())
                .limit(max(1, min(int(limit), 50)))
            ).all()
            return [
                self._batch_payload(
                    batch,
                    session.scalars(
                        select(StandardResourceBatchItem)
                        .where(StandardResourceBatchItem.batch_id == batch.batch_id)
                        .order_by(StandardResourceBatchItem.leaf_id, StandardResourceBatchItem.standard_kind)
                    ).all(),
                )
                for batch in batches
            ]

    def active_slot_keys(self, *, course_id: str) -> set[str]:
        prefix = f"{course_id}:%"
        with database_session(engine=self._engine) as session:
            return set(session.scalars(
                select(StandardResourceBatchItem.active_slot_key).where(
                    StandardResourceBatchItem.active_slot_key.like(prefix)
                )
            ).all())

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

    def claim_retry(self, *, course_id: str, batch_item_id: str) -> dict[str, Any]:
        """Atomically reserve a failed slot before resubmitting it."""
        now = _now()
        try:
            with database_session(engine=self._engine) as session:
                item = session.get(StandardResourceBatchItem, batch_item_id)
                if item is None:
                    raise StandardResourceRuleError(
                        "BATCH_ITEM_NOT_FOUND", "Batch item was not found"
                    )
                if item.status != "failed":
                    raise StandardResourceRuleError(
                        "BATCH_ITEM_NOT_RETRYABLE", "Only failed batch items can be retried"
                    )
                item.active_slot_key = f"{course_id}:{item.leaf_id}:{item.standard_kind}"
                item.status = "queued"
                item.error = None
                item.finished_at = None
                item.updated_at = now
                self._recount(session, item.batch_id, now=now)
                payload = self._item_payload(item)
        except IntegrityError as exc:
            raise StandardResourceRuleError(
                "SLOT_GENERATION_ACTIVE",
                "This knowledge resource is already being generated",
            ) from exc
        return payload

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
            item.active_slot_key = None
            item.finished_at = now
            item.updated_at = now
            self._recount(session, item.batch_id, now=now)

    def mark_succeeded(
        self,
        *,
        batch_item_id: str,
        material_version: int | None = None,
        content_hash: str | None = None,
    ) -> None:
        now = _now()
        with database_session(engine=self._engine) as session:
            item = session.get(StandardResourceBatchItem, batch_item_id)
            if item is None:
                raise StandardResourceRuleError("BATCH_ITEM_NOT_FOUND", "Batch item was not found")
            item.status = "succeeded"
            item.error = None
            item.material_version = material_version
            item.content_hash = str(content_hash or "").strip() or None
            item.active_slot_key = None
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
        expected_version: int | None = None,
        expected_content_hash: str | None = None,
    ) -> dict[str, Any]:
        return self.review_material_with_manifest(
            course_id=course_id,
            material_id=material_id,
            reviewer_id=reviewer_id,
            decision=decision,
            reason=reason,
            manifest=None,
            expected_version=expected_version,
            expected_content_hash=expected_content_hash,
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
        expected_version: int | None = None,
        expected_content_hash: str | None = None,
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
            if expected_version is not None and material.version != int(expected_version):
                raise StandardResourceRuleError(
                    "VERSION_CHANGED", "The resource changed after it was previewed"
                )
            if expected_content_hash and material.content_hash != str(expected_content_hash):
                raise StandardResourceRuleError(
                    "VERSION_CHANGED", "The resource changed after it was previewed"
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
                                "completion_rule": manifest.completion_rule,
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
        return [
            item["material_id"]
            for item in self.list_pending_targets_in_batch(
                course_id=course_id, batch_id=batch_id
            )
        ]

    def list_pending_targets_in_batch(
        self, *, course_id: str, batch_id: str
    ) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            items = session.scalars(
                select(StandardResourceBatchItem).where(
                    StandardResourceBatchItem.batch_id == batch_id,
                    StandardResourceBatchItem.status == "succeeded",
                    StandardResourceBatchItem.material_version.is_not(None),
                )
            ).all()
            result: list[dict[str, Any]] = []
            for item in items:
                material = session.scalar(
                    select(Material).where(
                        Material.course_id == course_id,
                        Material.material_type == item.material_type,
                        Material.material_id == item.material_id,
                        Material.origin_type == "standard",
                        Material.current_review_status == "pending",
                    )
                )
                if (
                    material is not None
                    and material.version == item.material_version
                    and material.content_hash == item.content_hash
                ):
                    result.append(
                        {
                            "material_id": item.material_id,
                            "version": item.material_version,
                            "content_hash": item.content_hash,
                        }
                    )
            return result

    def approve_pending_in_batch(
        self, *, course_id: str, batch_id: str, reviewer_id: str
    ) -> list[dict[str, Any]]:
        targets = self.list_pending_targets_in_batch(
            course_id=course_id, batch_id=batch_id
        )
        return [
            self.review_material(
                course_id=course_id,
                material_id=target["material_id"],
                reviewer_id=reviewer_id,
                decision="approved",
                expected_version=int(target["version"]),
                expected_content_hash=str(target["content_hash"]),
            )
            for target in targets
        ]
