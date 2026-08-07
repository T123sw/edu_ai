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


def _extract_response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            _clean(item.get("text") if isinstance(item, dict) else item)
            for item in content
            if _clean(item.get("text") if isinstance(item, dict) else item)
        )
    return _clean(content)


class KnowledgeBaseDirectFlashcardServiceV2:
    def __init__(self, *, content_provider=None, llm=None, course_storage_manager=None):
        self.content_provider = content_provider or KnowledgeBaseDocumentContentProvider()
        self.llm = llm or get_fallback_llm()
        self.course_storage_manager = course_storage_manager or default_course_storage_manager

    def generate(self, payload, *, job_id: str, config_snapshot_id: str) -> dict[str, Any]:
        selected_doc_ids = [
            _clean(item)
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if _clean(item)
        ]
        if self.llm is None:
            raise RuntimeError("flashcard_llm_unavailable")

        owner = _clean(getattr(payload, "owner", ""))
        document_result = {"documents": [], "truncated": False}
        if selected_doc_ids:
            document_result = self.content_provider.get_selected_document_contents(
                selected_doc_ids=selected_doc_ids,
                owner=owner or None,
            )
        documents = list(document_result.get("documents") or [])
        if selected_doc_ids and not documents:
            raise ValueError("selected documents content is empty")

        config = dict(getattr(payload, "flashcard_config", {}) or {})
        requested_count = max(3, min(30, int(config.get("count") or 10)))
        title = _clean(config.get("title")) or self._fallback_title(documents)
        cards = self._generate_cards(
            documents=documents,
            title=title,
            count=requested_count,
            difficulty=_clean(config.get("difficulty")) or "medium",
            category=_clean(config.get("category")),
            show_sources=bool(config.get("show_sources", True)),
            selected_doc_ids=selected_doc_ids,
        )
        material_id = (
            _clean(getattr(payload, "material_id", ""))
            or f"flashcard-{uuid4().hex[:16]}"
        )
        content = {
            "title": title,
            "cards": cards,
            "count": len(cards),
            "difficulty": _clean(config.get("difficulty")) or "medium",
            "show_sources": bool(config.get("show_sources", True)),
        }
        generation_state = {
            "status": "completed",
            "mode": "knowledge_base_direct",
            "requested_count": requested_count,
            "generated_count": len(cards),
        }
        saved = bool(
            self.course_storage_manager.save_generated_material(
                course_id=_clean(getattr(payload, "course_id", "")),
                material_type="flashcard",
                material_id=material_id,
                scope_type=_clean(getattr(payload, "scope_type", "")) or SCOPE_TYPE_COURSE,
                scope_id=_clean(getattr(payload, "scope_id", "")) or None,
                owner_user_id=owner or None,
                source_job_id=job_id,
                config_snapshot_id=config_snapshot_id,
                material_data={
                    "title": title,
                    "content": content,
                    "generation_state": generation_state,
                    "source": {
                        "selected_doc_ids": selected_doc_ids,
                        "documents_used": [
                            _clean(item.get("title"))
                            for item in documents
                            if _clean(item.get("title"))
                        ],
                    },
                },
            )
        )
        artifact = {
            "artifact_id": material_id,
            "artifact_type": "flashcard",
            "title": title,
            "content": content,
            "generation_state": generation_state,
        }
        return {
            "action": {"name": "generate.flashcard.direct"},
            "artifacts": [artifact],
            "saved": saved,
            "error": None if saved else "course material manifest write failed",
            "result_ref": {
                "resource_type": "course_material" if saved else "generated_artifact",
                "course_id": _clean(getattr(payload, "course_id", "")),
                "material_type": "flashcard",
                "material_id": material_id,
            },
            "trace": {
                "path": "direct",
                "selected_doc_count": len(selected_doc_ids),
                "content_doc_count": len(documents),
                "content_truncated": bool(document_result.get("truncated")),
            },
        }

    def _generate_cards(
        self,
        *,
        documents: list[dict[str, Any]],
        title: str,
        count: int,
        difficulty: str,
        category: str,
        show_sources: bool,
        selected_doc_ids: list[str],
    ) -> list[dict[str, Any]]:
        document_blocks = []
        for index, document in enumerate(documents, start=1):
            document_blocks.append(
                "\n".join(
                    [
                        f"文档 {index} ID：{_clean(document.get('doc_id'))}",
                        f"标题：{_clean(document.get('title'))}",
                        f"摘要：{_clean(document.get('summary'))}",
                        f"正文：{_clean(document.get('content'))}",
                    ]
                )
            )
        grounding_instruction = (
            "严格依据提供的文档生成复习卡。不得编造文档外事实。"
            if document_blocks
            else "本次未提供课程资料，请围绕用户指定的标题生成复习卡。"
            "不要声称内容来自未提供的课程资料。"
        )
        source_section = (
            "\n\n".join(document_blocks)
            if document_blocks
            else "本次不使用课程资料。"
        )
        response = self.llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "你是一名教师闪卡设计助手。"
                        f"{grounding_instruction}"
                        "只返回 JSON：{\"cards\":[{\"front\":\"问题\","
                        "\"back\":\"简洁准确的答案\",\"category\":\"分类\","
                        "\"source_doc_id\":\"文档ID\"}]}。"
                        "正反面不得为空，不得编造文档外事实，避免重复卡片。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{title}\n数量：{count}\n难度：{difficulty}\n"
                        f"分类偏好：{category or '自动分类'}\n\n"
                        + source_section
                    ),
                },
            ]
        )
        text = _extract_response_text(response)
        try:
            if "{" in text and "}" in text:
                text = text[text.find("{") : text.rfind("}") + 1]
            raw_cards = list((json.loads(text) or {}).get("cards") or [])
        except Exception as exc:
            raise ValueError("flashcard response is not valid JSON") from exc

        cards: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        allowed_sources = set(selected_doc_ids)
        for index, item in enumerate(raw_cards):
            if not isinstance(item, dict):
                continue
            front = _clean(item.get("front"))
            back = _clean(item.get("back"))
            if not front or not back or (front, back) in seen:
                continue
            seen.add((front, back))
            source_doc_id = _clean(item.get("source_doc_id"))
            cards.append(
                {
                    "id": f"card-{index + 1}",
                    "front": front,
                    "back": back,
                    "category": _clean(item.get("category")) or category or "未分类",
                    "source_doc_id": (
                        source_doc_id
                        if show_sources and source_doc_id in allowed_sources
                        else None
                    ),
                }
            )
            if len(cards) >= count:
                break
        if not cards:
            raise ValueError("flashcard response contains no valid cards")
        if len(cards) != count:
            raise ValueError(
                f"flashcard response count mismatch: expected {count}, got {len(cards)}"
            )
        return cards

    @staticmethod
    def _fallback_title(documents: list[dict[str, Any]]) -> str:
        first_title = _clean(documents[0].get("title")) if documents else ""
        return f"{first_title or '课程知识'}复习闪卡"


def build_default_knowledge_base_direct_flashcard_service_v2():
    return KnowledgeBaseDirectFlashcardServiceV2(
        content_provider=KnowledgeBaseDocumentContentProvider(),
        llm=get_fallback_llm(),
        course_storage_manager=default_course_storage_manager,
    )
