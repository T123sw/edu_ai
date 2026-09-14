"""Orchestration for asynchronous standard-resource generation batches."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from .models import STANDARD_KINDS, LeafNode, StandardKind, extract_leaf_nodes, stable_material_id, standard_material_type
from .repository import StandardResourceRepository, StandardResourceRuleError


Submitter = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]
JobLookup = Callable[[str], Any | None]
GraphLookup = Callable[[str], dict[str, Any] | None]
MaterialList = Callable[[str], list[dict[str, Any]]]
MaterialGet = Callable[[str, str, str], dict[str, Any] | None]
VersionLookup = Callable[[str, str, str, int], dict[str, Any] | None]

_TITLE_SUFFIX = {
    "classroom": "AI 课堂",
    "study_guide": "学习指南",
    "practice": "练习",
}

_DEFAULT_KIND_RUNTIME_SECONDS = {
    "classroom": 3600,
    "study_guide": 900,
    "practice": 900,
}
MAX_STANDARD_RESOURCE_BATCH_DEADLINE_SECONDS = 86400


def standard_resource_execution_timeout_seconds(standard_kind: str) -> int:
    return _DEFAULT_KIND_RUNTIME_SECONDS.get(
        str(standard_kind or ""),
        _DEFAULT_KIND_RUNTIME_SECONDS["study_guide"],
    )


class StandardResourceBatchService:
    def __init__(
        self,
        *,
        repository: StandardResourceRepository,
        graph_lookup: GraphLookup,
        submitter: Submitter,
        job_lookup: JobLookup,
        material_list: MaterialList | None = None,
        material_get: MaterialGet | None = None,
        version_lookup: VersionLookup | None = None,
    ):
        self.repository = repository
        self.graph_lookup = graph_lookup
        self.submitter = submitter
        self.job_lookup = job_lookup
        self.material_list = material_list or (lambda _course_id: [])
        self.material_get = material_get or (lambda _course_id, _material_type, _material_id: None)
        self.version_lookup = version_lookup or (
            lambda _course_id, _material_type, _material_id, _version: None
        )

    @staticmethod
    def _graph_version(graph: dict[str, Any] | None) -> str:
        explicit = str((graph or {}).get("version") or (graph or {}).get("graph_version") or "").strip()
        if explicit:
            return explicit
        canonical = json.dumps(graph or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _selected_kinds(values: list[str] | None) -> list[str]:
        requested = list(dict.fromkeys(str(item).strip() for item in (values or []) if str(item).strip()))
        if not requested:
            requested = [item.value for item in STANDARD_KINDS]
        try:
            return [StandardKind(item).value for item in requested]
        except ValueError as exc:
            raise StandardResourceRuleError("INVALID_STANDARD_KIND", str(exc)) from exc

    @staticmethod
    def _resolve_selected_leaves(
        leaves: list[LeafNode], leaf_ids: list[str]
    ) -> list[LeafNode]:
        if not leaves:
            raise StandardResourceRuleError(
                "COURSE_HAS_NO_LEAVES",
                "The course knowledge structure has no leaf knowledge points",
            )
        requested = list(
            dict.fromkeys(
                str(item).strip() for item in leaf_ids if str(item).strip()
            )
        )
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
    def _baseline_summary(material: dict[str, Any] | None) -> str | None:
        if not material:
            return None
        payload = {
            key: material.get(key)
            for key in ("title", "content", "stage", "scenes")
            if material.get(key) is not None
        }
        if not payload:
            return None
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return serialized[:12000]

    def preview_batch(
        self,
        *,
        course_id: str,
        leaf_ids: list[str],
        standard_kinds: list[str] | None = None,
        mode: str = "fill_missing",
    ) -> dict[str, Any]:
        if mode not in {"fill_missing", "repair_rejected", "regenerate_all"}:
            raise StandardResourceRuleError("INVALID_GENERATION_MODE", "Unknown regeneration mode")
        graph = self.graph_lookup(course_id)
        leaves = extract_leaf_nodes(graph)
        selected = self._resolve_selected_leaves(leaves, leaf_ids)
        kinds = self._selected_kinds(standard_kinds)
        materials = {
            (str(item.get("material_type") or ""), str(item.get("material_id") or "")): item
            for item in self.material_list(course_id)
            if item.get("origin_type") == "standard"
        }
        active = self.repository.active_slot_keys(course_id=course_id)
        items: list[dict[str, Any]] = []
        counts = {key: 0 for key in ("generate", "repair", "regenerate", "keep", "blocked")}
        by_id = {leaf.leaf_id: leaf for leaf in leaves}
        for selected_leaf in selected:
            leaf = by_id[selected_leaf.leaf_id]
            bundle_spec = {
                "skill": "edu-standard-resource-bundle",
                "skill_version": "1.0.0",
                "course_id": course_id,
                "subject": leaf.title,
                "path_titles": list(leaf.path_titles),
                "audience": "课程学生",
                "prerequisites": list(leaf.path_titles[:-1]),
                "objectives": [
                    f"准确解释“{leaf.title}”的核心概念、必要前提和适用边界",
                    f"在典型学习任务中应用“{leaf.title}”并说明推理过程",
                    f"识别“{leaf.title}”的常见误区并通过练习完成自我校正",
                ],
                "alignment": {
                    "classroom": "建立概念理解并通过互动检查",
                    "study_guide": "提供可复习的解释、例子、边界与清单",
                    "practice": "逐项目标取证，答案与解析可独立核验",
                },
                "content_boundary": f"聚焦叶子知识点“{leaf.title}”，父级路径仅用于消歧和先修语境",
                "example_strategy": "至少提供一个典型例子和一个边界或误区反例",
                "misconception_strategy": "指出易混概念、错误前提或常见推理跳步，并给出校正依据",
                "source_scope": {"mode": "course_auto", "web_search": False},
            }
            for kind in kinds:
                material_type = standard_material_type(kind)
                material_id = stable_material_id(leaf.leaf_id, kind)
                material = materials.get((material_type, material_id))
                status = str((material or {}).get("current_review_status") or "not_generated")
                slot_key = f"{course_id}:{leaf.leaf_id}:{kind}"
                if slot_key in active or status == "pending":
                    action, reason = "blocked", "已有生成中或待审核候选，请先处理当前版本"
                elif material is None:
                    action, reason = "generate", "资源尚未生成"
                elif status == "rejected" and mode == "repair_rejected":
                    action, reason = "repair", "根据最近退回意见生成修订候选"
                elif mode == "regenerate_all":
                    action, reason = "regenerate", "明确为已有资源创建候选新版"
                else:
                    action, reason = "keep", "保留已有资源"
                counts[action] += 1
                current_version = int(material.get("version") or 0) if material else None
                approved_version = (
                    int(material["approved_version"])
                    if material and material.get("approved_version") is not None
                    else None
                )
                rejection_reason = None
                if material and current_version:
                    version = self.version_lookup(course_id, material_type, material_id, current_version)
                    rejection_reason = (version or {}).get("rejection_reason")
                items.append({
                    "leaf_id": leaf.leaf_id,
                    "leaf_title": leaf.title,
                    "standard_kind": kind,
                    "material_type": material_type,
                    "material_id": material_id,
                    "action": action,
                    "reason": reason,
                    "current_version": current_version,
                    "approved_version": approved_version,
                    "content_hash": str((material or {}).get("content_hash") or "") or None,
                    "base_version": current_version,
                    "generation_context": {
                        "path_titles": list(leaf.path_titles),
                        "bundle_spec": bundle_spec,
                        "baseline_version": current_version,
                        "baseline_content_hash": str((material or {}).get("content_hash") or "") or None,
                        "baseline_summary": self._baseline_summary(material),
                        "approved_version": approved_version,
                        "rejection_reason": rejection_reason,
                    },
                })
        return {
            "course_id": course_id,
            "graph_version": self._graph_version(graph),
            "mode": mode,
            "standard_kinds": kinds,
            "generate_items": counts["generate"],
            "repair_items": counts["repair"],
            "regenerate_items": counts["regenerate"],
            "kept_items": counts["keep"],
            "blocked_items": counts["blocked"],
            "actionable_items": counts["generate"] + counts["repair"] + counts["regenerate"],
            "items": items,
        }

    @staticmethod
    def _execution_timeout_seconds(item: dict[str, Any]) -> int:
        return standard_resource_execution_timeout_seconds(
            str(item.get("standard_kind") or "")
        )

    def _selected_leaves(self, course_id: str, leaf_ids: list[str]):
        return self._resolve_selected_leaves(
            extract_leaf_nodes(self.graph_lookup(course_id)), leaf_ids
        )

    @staticmethod
    def _context(
        *,
        item: dict[str, Any],
        course_id: str,
        created_by: str,
        batch_id: str,
        deadline_seconds: int,
        execution_timeout_seconds: int,
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
            "deadline_seconds": deadline_seconds,
            "execution_timeout_seconds": execution_timeout_seconds,
            "title": f'{item["leaf_title"]}{_TITLE_SUFFIX[item["standard_kind"]]}',
            "idempotency_key": (
                f'{batch_id}:{item["leaf_id"]}:{item["standard_kind"]}:'
                f'{int(item["attempt_count"]) + 1}'
            ),
            "action": item.get("action") or "generate",
            "base_version": item.get("base_version"),
            "generation_context": dict(item.get("generation_context") or {}),
        }

    async def _submit_item(
        self,
        *,
        item: dict[str, Any],
        course_id: str,
        created_by: str,
        batch_id: str,
        deadline_seconds: int,
        execution_timeout_seconds: int,
    ) -> None:
        context = self._context(
            item=item,
            course_id=course_id,
            created_by=created_by,
            batch_id=batch_id,
            deadline_seconds=deadline_seconds,
            execution_timeout_seconds=execution_timeout_seconds,
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
        standard_kinds: list[str] | None = None,
        mode: str = "fill_missing",
        idempotency_key: str | None = None,
        expected_graph_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_idempotency_key = str(idempotency_key or "").strip()
        if normalized_idempotency_key:
            existing = self.repository.find_batch_by_idempotency(
                course_id=course_id,
                idempotency_key=normalized_idempotency_key,
            )
            if existing is not None:
                return self.get_batch(course_id=course_id, batch_id=existing["batch_id"])
        preview = self.preview_batch(
            course_id=course_id,
            leaf_ids=leaf_ids,
            standard_kinds=standard_kinds,
            mode=mode,
        )
        if expected_graph_version and expected_graph_version != preview["graph_version"]:
            raise StandardResourceRuleError(
                "GRAPH_VERSION_CHANGED", "The course knowledge structure changed after preview"
            )
        actionable = [item for item in preview["items"] if item["action"] in {"generate", "repair", "regenerate"}]
        if not actionable:
            raise StandardResourceRuleError(
                "NO_ACTIONABLE_RESOURCES", "No selected resource needs generation"
            )
        leaves = list(
            {
                item["leaf_id"]: LeafNode(
                    leaf_id=item["leaf_id"],
                    title=item["leaf_title"],
                    chapter_id=None,
                    chapter_title=None,
                    path_titles=tuple(
                        (item.get("generation_context") or {}).get("path_titles") or []
                    ),
                )
                for item in actionable
            }.values()
        )
        batch = self.repository.create_batch(
            course_id=course_id,
            created_by=created_by,
            leaves=leaves,
            planned_items=actionable,
            idempotency_key=normalized_idempotency_key or f"legacy-{uuid4().hex}",
            graph_version=preview["graph_version"],
            generation_mode=mode,
        )
        if not batch.get("_was_created", True):
            return self.get_batch(course_id=course_id, batch_id=batch["batch_id"])
        for item in batch["items"]:
            await self._submit_item(
                item=item,
                course_id=course_id,
                created_by=created_by,
                batch_id=batch["batch_id"],
                deadline_seconds=MAX_STANDARD_RESOURCE_BATCH_DEADLINE_SECONDS,
                execution_timeout_seconds=self._execution_timeout_seconds(item),
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
                reference = dict(getattr(job, "result_ref", None) or {})
                material = self.material_get(
                    course_id, item["material_type"], item["material_id"]
                )
                version = reference.get("version") or (material or {}).get("version")
                content_hash = reference.get("content_hash") or (material or {}).get("content_hash")
                matches = (
                    material is not None
                    and str(material.get("generation_batch_id") or "") == batch_id
                    and str(material.get("source_job_id") or "") == str(item["job_id"])
                    and version
                    and content_hash
                    and int(material.get("version") or 0) == int(version)
                    and str(material.get("content_hash") or "") == str(content_hash)
                )
                if matches:
                    self.repository.mark_succeeded(
                        batch_item_id=item["batch_item_id"],
                        material_version=int(version),
                        content_hash=str(content_hash),
                    )
                else:
                    self.repository.mark_failed(
                        batch_item_id=item["batch_item_id"],
                        code="RESULT_VERSION_MISMATCH",
                        message="Generated material could not be bound to this batch item",
                    )
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
        failed_items = [item for item in batch["items"] if item["status"] == "failed"]
        for item in failed_items:
            retry_plan = self.preview_batch(
                course_id=course_id,
                leaf_ids=[item["leaf_id"]],
                standard_kinds=[item["standard_kind"]],
                mode=batch["generation_mode"],
            )["items"][0]
            if retry_plan["action"] not in {"generate", "repair", "regenerate"}:
                raise StandardResourceRuleError(
                    "SLOT_GENERATION_ACTIVE",
                    "The failed item can no longer be retried because its slot changed",
                )
            claimed = self.repository.claim_retry(
                course_id=course_id,
                batch_item_id=item["batch_item_id"],
            )
            await self._submit_item(
                item=claimed,
                course_id=course_id,
                created_by=requested_by,
                batch_id=batch_id,
                deadline_seconds=MAX_STANDARD_RESOURCE_BATCH_DEADLINE_SECONDS,
                execution_timeout_seconds=self._execution_timeout_seconds(item),
            )
        return self.get_batch(course_id=course_id, batch_id=batch_id)
