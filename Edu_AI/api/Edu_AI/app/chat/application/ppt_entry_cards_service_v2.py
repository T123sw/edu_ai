from __future__ import annotations

from typing import Any

from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider


def _build_preset_cards() -> list[dict[str, Any]]:
    return [
        {
            "card_id": "preset-knowledge-lecture",
            "card_type": "preset",
            "title": "知识讲解型",
            "description": "适合概念定义、原理机制和课堂讲解。",
            "objective_hint": "课堂讲解",
            "length_option": "medium",
            "preset_key": "knowledge_lecture",
            "style_hint": "讲解清晰、层次分明",
        },
        {
            "card_id": "preset-topic-briefing",
            "card_type": "preset",
            "title": "主题分享型",
            "description": "适合专题分享、课程汇报和公开展示。",
            "objective_hint": "主题分享",
            "length_option": "medium",
            "preset_key": "topic_briefing",
            "style_hint": "重点突出、逻辑顺畅",
        },
        {
            "card_id": "preset-comparison-analysis",
            "card_type": "preset",
            "title": "对比分析型",
            "description": "适合多方案、多文档、多观点的差异分析。",
            "objective_hint": "对比分析",
            "length_option": "long",
            "preset_key": "comparison_analysis",
            "style_hint": "结构清楚、结论明确",
        },
        {
            "card_id": "preset-defense-summary",
            "card_type": "preset",
            "title": "汇报答辩型",
            "description": "适合结课汇报、项目展示和答辩总结。",
            "objective_hint": "汇报答辩",
            "length_option": "short",
            "preset_key": "defense_summary",
            "style_hint": "结论先行、表达凝练",
        },
    ]


class PptEntryCardsServiceV2:
    def __init__(self, *, summary_provider=None):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()

    def get_cards(self, payload) -> dict[str, Any]:
        selected_doc_ids = [
            str(item or "").strip()
            for item in list(getattr(payload, "selected_doc_ids", []) or [])
            if str(item or "").strip()
        ]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")

        owner = str(getattr(payload, "owner", "") or "").strip() or None
        summary_result = self.summary_provider.get_selected_document_summaries(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(summary_result.get("documents") or [])
        recommended_cards = self._build_recommended_cards(documents=documents, selected_doc_ids=selected_doc_ids)
        return {
            "entry_mode": "knowledge_base_ppt",
            "cards": [*_build_preset_cards(), *recommended_cards],
            "trace": {
                "selected_doc_count": len(selected_doc_ids),
                "summary_doc_count": len(documents),
                "fallback_used": bool(summary_result.get("fallback_used")),
            },
        }

    def _build_recommended_cards(self, *, documents: list[dict[str, Any]], selected_doc_ids: list[str]) -> list[dict[str, Any]]:
        combined = " ".join(
            [
                str(item.get("title") or "").strip()
                + " "
                + str(item.get("summary") or "").strip()
                for item in documents
            ]
        )
        cards: list[dict[str, Any]] = []
        if len(selected_doc_ids) > 1:
            cards.append(
                {
                    "card_id": "rec-comparison-view",
                    "card_type": "recommended",
                    "title": "多材料对比讲解",
                    "description": "文档来源较多，适合做差异、共性和结论总结。",
                    "objective_hint": "对比分析",
                    "length_option": "long",
                    "recommendation_type": "comparison_view",
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high",
                    "style_hint": "先归类后对比，最后形成结论",
                }
            )
        lowered = combined.lower()
        if any(token in combined for token in ("流程", "步骤", "机制", "过程")):
            cards.append(
                {
                    "card_id": "rec-process-flow",
                    "card_type": "recommended",
                    "title": "流程机制讲解",
                    "description": "材料强调流程或机制，适合做分步骤说明。",
                    "objective_hint": "课堂讲解",
                    "length_option": "medium",
                    "recommendation_type": "process_flow",
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high",
                    "style_hint": "强调前后关系和步骤衔接",
                }
            )
        if any(token in combined for token in ("案例", "应用", "实践", "场景")):
            cards.append(
                {
                    "card_id": "rec-case-application",
                    "card_type": "recommended",
                    "title": "案例应用讲解",
                    "description": "材料包含案例或应用场景，适合做场景化 PPT。",
                    "objective_hint": "主题分享",
                    "length_option": "medium",
                    "recommendation_type": "case_application",
                    "recommendation_source": "doc_summaries",
                    "fit_score": "medium",
                    "style_hint": "案例驱动，强调问题与应用价值",
                }
            )
        if not cards:
            cards.append(
                {
                    "card_id": "rec-concept-focus",
                    "card_type": "recommended",
                    "title": "核心概念梳理",
                    "description": "材料更适合概念定义、框架梳理和重点讲解。",
                    "objective_hint": "课堂讲解",
                    "length_option": "medium",
                    "recommendation_type": "concept_focus",
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high",
                    "style_hint": "概念清晰、层层展开",
                }
            )
        return cards


def build_default_ppt_entry_cards_service_v2() -> PptEntryCardsServiceV2:
    return PptEntryCardsServiceV2(summary_provider=KnowledgeBaseSummaryProvider())
