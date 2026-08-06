from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.knowledge_base_document_content_provider import (
    KnowledgeBaseDocumentContentProvider,
)
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.course_storage import storage_manager as default_course_storage_manager


def _clean(value: Any) -> str:
    return str(value or "").strip()


class KnowledgeBaseDirectGraphServiceV2:
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def generate(self, payload, *, job_id: str, config_snapshot_id: str):
        owner = _clean(getattr(payload, "owner", ""))
        selected_doc_ids = [
            _clean(item)
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if _clean(item)
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")
        documents = list(
            self.content_provider.get_selected_document_contents(
                selected_doc_ids=selected_doc_ids,
                owner=owner or None,
            ).get("documents")
            or []
        )
        if not documents or self.llm is None:
            raise ValueError("selected documents content is empty")
        config = dict(getattr(payload, "graph_config", {}) or {})
        title = _clean(config.get("title")) or f"{_clean(documents[0].get('title'))}思维导图"
        max_depth = max(2, min(5, int(config.get("max_depth") or 3)))
        prompt_docs = "\n\n".join(
            f"文档：{_clean(item.get('title'))}\n{_clean(item.get('content'))}"
            for item in documents
        )
        raw = self.llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "严格基于资料生成教学思维导图，只返回 JSON。"
                        '结构固定为 {"title":"根节点","children":[{"title":"节点","summary":"说明","children":[]}]}。'
                        "节点标题非空、同级不重复，不得编造资料外事实。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"标题：{title}\n最大层级：{max_depth}\n{prompt_docs}",
                },
            ]
        )
        text = _clean(getattr(raw, "content", raw))
        try:
            text = text[text.find("{") : text.rfind("}") + 1]
            root = json.loads(text)
        except Exception as exc:
            raise ValueError("graph response is not valid JSON") from exc
        normalized_root = self._normalize_node(root, depth=1, max_depth=max_depth)
        material_id = (
            _clean(getattr(payload, "material_id", ""))
            or f"graph-{uuid4().hex[:16]}"
        )
        content = {"root": normalized_root, "max_depth": max_depth}
        saved = bool(
            self.course_storage_manager.save_generated_material(
                course_id=_clean(getattr(payload, "course_id", "")),
                material_type="graph",
                material_id=material_id,
                scope_type=_clean(getattr(payload, "scope_type", "")) or SCOPE_TYPE_COURSE,
                scope_id=_clean(getattr(payload, "scope_id", "")) or None,
                owner_user_id=owner,
                source_job_id=job_id,
                config_snapshot_id=config_snapshot_id,
                material_data={
                    "title": title,
                    "content": content,
                    "generation_state": {"status": "completed", "mode": "knowledge_base_direct"},
                    "source": {"selected_doc_ids": selected_doc_ids},
                },
            )
        )
        return {
            "saved": saved,
            "error": None if saved else "course material manifest write failed",
            "artifacts": [{"artifact_id": material_id, "artifact_type": "graph", "title": title, "content": content}],
            "result_ref": {
                "resource_type": "course_material" if saved else "generated_artifact",
                "course_id": _clean(getattr(payload, "course_id", "")),
                "material_type": "graph",
                "material_id": material_id,
            },
        }

    def _normalize_node(self, value: Any, *, depth: int, max_depth: int):
        if not isinstance(value, dict) or not _clean(value.get("title")):
            raise ValueError("graph contains an invalid node")
        children = []
        seen = set()
        if depth < max_depth:
            for item in list(value.get("children") or []):
                title = _clean(item.get("title")) if isinstance(item, dict) else ""
                if not title or title in seen:
                    continue
                seen.add(title)
                children.append(self._normalize_node(item, depth=depth + 1, max_depth=max_depth))
        return {
            "title": _clean(value.get("title")),
            "summary": _clean(value.get("summary")) or None,
            "children": children,
        }


def build_default_knowledge_base_direct_graph_service_v2():
    return KnowledgeBaseDirectGraphServiceV2()

