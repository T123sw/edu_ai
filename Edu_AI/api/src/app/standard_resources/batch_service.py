"""Orchestration for asynchronous standard-resource generation batches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .models import extract_leaf_nodes
from .repository import StandardResourceRepository, StandardResourceRuleError


Submitter = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]
JobLookup = Callable[[str], Any | None]
GraphLookup = Callable[[str], dict[str, Any] | None]

_TITLE_SUFFIX = {
    "classroom": "AI 课堂",
    "study_guide": "学习指南",
    "practice": "练习",
}


class StandardResourceBatchService:
    def __init__(
        self,
        *,
        repository: StandardResourceRepository,
        graph_lookup: GraphLookup,
        submitter: Submitter,
        job_lookup: JobLookup,
    ):
        self.repository = repository
        self.graph_lookup = graph_lookup
        self.submitter = submitter
        self.job_lookup = job_lookup

    def _selected_leaves(self, course_id: str, leaf_ids: list[str]):
        leaves = extract_leaf_nodes(self.graph_lookup(course_id))
        if not leaves:
            raise StandardResourceRuleError(
                "COURSE_HAS_NO_LEAVES",
                "The course knowledge structure has no leaf knowledge points",
            )
        requested = list(dict.fromkeys(str(item).strip() for item in leaf_ids if str(item).strip()))
        if not requested:
            return leaves
        by_id = {item.leaf_id: item for item in leaves}
        missing = [item for item in requested if item not in by_id]
        if missing:
            raise StandardResourceRuleError(
                "LEAF_NOT_FOUND",
                f"Unknown leaf knowledge point: {', '.join(missing)}",
            )
        return [by_id[item] for item in requested]

    @staticmethod
    def _context(
        *,
        item: dict[str, Any],
        course_id: str,
        created_by: str,
        batch_id: str,
    ) -> dict[str, Any]:
        return {
            "course_id": course_id,
            "owner_user_id": created_by,
            "scope_type": "knowledge_point",
            "scope_id": item["leaf_id"],
            "origin_type": "standard",
            "standard_kind": item["standard_kind"],
            "generation_batch_id": batch_id,
            "current_review_status": "pending",
            "review_status": "pending",
            "title": f'{item["leaf_title"]}{_TITLE_SUFFIX[item["standard_kind"]]}',
            "idempotency_key": (
                f'{batch_id}:{item["leaf_id"]}:{item["standard_kind"]}:'
                f'{int(item["attempt_count"]) + 1}'
            ),
        }

    async def _submit_item(
        self,
        *,
        item: dict[str, Any],
        course_id: str,
        created_by: str,
        batch_id: str,
    ) -> None:
        context = self._context(
            item=item,
            course_id=course_id,
            created_by=created_by,
            batch_id=batch_id,
        )
        try:
            job = await self.submitter(item, context)
            job_id = str(getattr(job, "edu_job_id", "") or "").strip()
            if not job_id and isinstance(job, dict):
                job_id = str(job.get("edu_job_id") or job.get("job_id") or "").strip()
            if not job_id:
                raise RuntimeError("generation submitter returned no job id")
            self.repository.mark_submitted(
                batch_item_id=item["batch_item_id"], job_id=job_id
            )
        except Exception as exc:
            self.repository.mark_failed(
                batch_item_id=item["batch_item_id"],
                code="SUBMISSION_FAILED",
                message=str(exc),
            )

    async def create_batch(
        self,
        *,
        course_id: str,
        created_by: str,
        leaf_ids: list[str],
    ) -> dict[str, Any]:
        leaves = self._selected_leaves(course_id, leaf_ids)
        batch = self.repository.create_batch(
            course_id=course_id,
            created_by=created_by,
            leaves=leaves,
        )
        for item in batch["items"]:
            await self._submit_item(
                item=item,
                course_id=course_id,
                created_by=created_by,
                batch_id=batch["batch_id"],
            )
        return self.get_batch(course_id=course_id, batch_id=batch["batch_id"])

    def get_batch(self, *, course_id: str, batch_id: str) -> dict[str, Any]:
        batch = self.repository.get_batch(course_id=course_id, batch_id=batch_id)
        if batch is None:
            raise StandardResourceRuleError("BATCH_NOT_FOUND", "Batch was not found")
        for item in batch["items"]:
            if item["status"] != "running" or not item.get("job_id"):
                continue
            job = self.job_lookup(item["job_id"])
            if job is None:
                continue
            raw_status = getattr(job, "status", None)
            status = str(getattr(raw_status, "value", raw_status) or "").lower()
            if status == "succeeded":
                self.repository.mark_succeeded(batch_item_id=item["batch_item_id"])
            elif status in {"failed", "canceled", "partially_succeeded"}:
                self.repository.mark_failed(
                    batch_item_id=item["batch_item_id"],
                    code=str(getattr(job, "error_code", None) or "GENERATION_FAILED"),
                    message=str(getattr(job, "error_message", None) or status),
                )
        refreshed = self.repository.get_batch(course_id=course_id, batch_id=batch_id)
        if refreshed is None:
            raise StandardResourceRuleError("BATCH_NOT_FOUND", "Batch was not found")
        return refreshed

    async def retry_failed(
        self,
        *,
        course_id: str,
        batch_id: str,
        requested_by: str,
    ) -> dict[str, Any]:
        batch = self.get_batch(course_id=course_id, batch_id=batch_id)
        for item in batch["items"]:
            if item["status"] != "failed":
                continue
            await self._submit_item(
                item=item,
                course_id=course_id,
                created_by=requested_by,
                batch_id=batch_id,
            )
        return self.get_batch(course_id=course_id, batch_id=batch_id)
