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
        document_result = {"documents": []}
        if selected_doc_ids:
            document_result = self.content_provider.get_selected_document_contents(
                selected_doc_ids=selected_doc_ids,
                owner=owner or None,
            )
        documents = list(document_result.get("documents") or [])
        if selected_doc_ids and not documents:
            raise ValueError("selected documents content is empty")
        research_context = _clean(getattr(payload, "research_context", ""))
        if self.llm is None:
            raise RuntimeError("graph_llm_unavailable")
        config = dict(getattr(payload, "graph_config", {}) or {})
        first_document_title = (
            _clean(documents[0].get("title")) if documents else ""
        )
        title = _clean(config.get("title")) or (
            f"{first_document_title}思维导图"
            if first_document_title
            else ""
        )
        if not title:
            raise ValueError("graph title is required when no documents are selected")
        description = _clean(config.get("description"))
        max_depth = max(2, min(5, int(config.get("max_depth") or 3)))
        prompt_docs = "\n\n".join(
            f"文档：{_clean(item.get('title'))}\n{_clean(item.get('content'))}"
            for item in documents
        )
        if research_context:
            prompt_docs = "\n\n".join(
                part for part in (
                    prompt_docs,
                    f"Agent research evidence:\n{research_context[:16000]}",
                ) if part
            )
        grounding_instruction = (
            "严格基于资料生成教学思维导图，不得编造资料外事实。"
            if documents or research_context
            else "本次未提供课程资料，请围绕用户指定主题生成教学思维导图。"
            "不要声称内容来自未提供的课程资料。"
        )
        source_section = prompt_docs or "本次不使用课程资料。"
        raw = self.llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        f"{grounding_instruction}只返回 JSON。"
                        '结构固定为 {"title":"根节点","children":[{"title":"节点","summary":"说明","children":[]}]}。'
                        "节点标题非空、同级不重复。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{title}\n说明：{description}\n最大层级：{max_depth}\n"
                        f"{source_section}"
                    ),
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
                    "generation_state": {
                        "status": "completed",
                        "mode": "knowledge_base_direct",
                        "research_context_used": bool(research_context),
                        "research_bundle_id": _clean(getattr(payload, "research_bundle_id", "")),
                    },
                    "source": {
                        "selected_doc_ids": selected_doc_ids,
                        "research_bundle_id": _clean(getattr(payload, "research_bundle_id", "")),
                    },
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

    def _normalize_node(
        self,
        value: Any,
        *,
        depth: int,
        max_depth: int,
        node_id: str = "root",
    ):
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
                children.append(
                    self._normalize_node(
                        item,
                        depth=depth + 1,
                        max_depth=max_depth,
                        node_id=f"{node_id}-{len(children) + 1}",
                    )
                )
        return {
            "id": node_id,
            "title": _clean(value.get("title")),
            "summary": _clean(value.get("summary")) or None,
            "children": children,
        }


def build_default_knowledge_base_direct_graph_service_v2():
    return KnowledgeBaseDirectGraphServiceV2()

