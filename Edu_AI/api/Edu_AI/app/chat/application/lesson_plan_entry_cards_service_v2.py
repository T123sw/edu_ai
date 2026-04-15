from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
from app.chat.application.lesson_plan_entry_recommendation_generator import (
    LessonPlanEntryRecommendationGenerator,
    build_default_lesson_plan_entry_recommendation_generator,
)

_PRESET_LIBRARY = [
    {
        "card_id": "preset-new-lesson",
        "card_type": "preset",
        "title": "新授课教案",
        "description": "适合围绕核心概念、关键材料和基础问题链展开单课时教学。",
        "prompt_draft": "请基于已选文档生成一份贴近真实课堂的新授课教案，先输出可确认的大纲，再生成完整正文。",
        "preset_key": "new_lesson",
        "lesson_type": "新授课",
        "default_objective": "帮助学生建立核心知识框架并完成基础理解",
        "style_hint": "突出问题链、材料使用和课堂产出",
    },
    {
        "card_id": "preset-review-lesson",
        "card_type": "preset",
        "title": "复习课教案",
        "description": "适合围绕知识梳理、易错点辨析和当堂检测组织教学。",
        "prompt_draft": "请基于已选文档生成一份复习课教案，突出知识结构、易错点和练习反馈。",
        "preset_key": "review_lesson",
        "lesson_type": "复习课",
        "default_objective": "帮助学生梳理结构、暴露误区并完成巩固迁移",
        "style_hint": "强化归纳整理、错因分析和当堂检测",
    },
    {
        "card_id": "preset-inquiry-lesson",
        "card_type": "preset",
        "title": "探究课教案",
        "description": "适合围绕材料辨析、观点比较和小组讨论组织课堂。",
        "prompt_draft": "请基于已选文档生成一份探究课教案，突出材料解读、课堂提问和学生讨论。",
        "preset_key": "inquiry_lesson",
        "lesson_type": "探究课",
        "default_objective": "帮助学生基于证据形成判断并完成课堂表达",
        "style_hint": "强调材料分析、追问纠偏和小组展示",
    },
    {
        "card_id": "preset-practice-lesson",
        "card_type": "preset",
        "title": "练习讲评教案",
        "description": "适合围绕典型题、常见错误和方法迁移组织教学。",
        "prompt_draft": "请基于已选文档生成一份练习讲评教案，突出典型问题、错因分析和巩固训练。",
        "preset_key": "practice_lesson",
        "lesson_type": "讲评课",
        "default_objective": "帮助学生定位问题、修正思路并迁移应用",
        "style_hint": "突出错因辨析、示范讲解和分层练习",
    },
]

_RECOMMENDATION_LIBRARY = {
    "knowledge_building": {
        "title": "知识建构教案",
        "description": "适合围绕概念解释、知识建模和基础理解组织新授课堂。",
        "prompt_draft": "请基于已选文档生成一份知识建构型教案，突出概念建立、示例讲解与课堂产出。",
        "lesson_type": "新授课",
        "style_hint": "从关键概念到应用示例逐步推进",
    },
    "historical_inquiry": {
        "title": "史料探究教案",
        "description": "适合围绕史料辨析、观点比较和证据表达组织课堂。",
        "prompt_draft": "请基于已选文档生成一份史料探究教案，突出史料解读、比较讨论和历史评价。",
        "lesson_type": "探究课",
        "style_hint": "突出史料对读、问题链追问和观点表达",
    },
    "practice_consolidation": {
        "title": "练习巩固教案",
        "description": "适合围绕题例训练、错误辨析和当堂巩固组织教学。",
        "prompt_draft": "请基于已选文档生成一份练习巩固教案，突出变式训练、错因讲评和即时反馈。",
        "lesson_type": "讲评课",
        "style_hint": "强调典型错误、方法归纳和分层练习",
    },
    "review_summary": {
        "title": "复习梳理教案",
        "description": "适合围绕知识结构、重点回顾和课堂检测组织复习课。",
        "prompt_draft": "请基于已选文档生成一份复习梳理教案，突出知识网络、重难点回顾和检测反馈。",
        "lesson_type": "复习课",
        "style_hint": "突出结构化梳理与课堂检测",
    },
    "material_analysis": {
        "title": "材料分析教案",
        "description": "适合围绕文本证据、材料批注和课堂表达组织教学。",
        "prompt_draft": "请基于已选文档生成一份材料分析教案，突出材料圈点、证据提炼和表达任务。",
        "lesson_type": "探究课",
        "style_hint": "聚焦材料证据、批注任务与展示汇报",
    },
}

_STOPWORDS = {
    "文档",
    "材料",
    "内容",
    "摘要",
    "知识",
    "主题",
    "课程",
    "课堂",
    "学习",
    "教学",
    "报告",
    "总结",
    "selected",
    "document",
    "documents",
    "summary",
    "content",
    "topic",
}


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_selected_doc_ids(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in list(values or []):
        text = _clean(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _extract_terms_from_text(text: str) -> list[str]:
    tokens = re.split(r"[\s,.;:!?，。；：、（）()【】\[\]{}<>]+", text or "")
    terms: list[str] = []
    for token in tokens:
        cleaned = _clean(token)
        if not cleaned or len(cleaned) < 2:
            continue
        if cleaned.lower() in _STOPWORDS or cleaned in _STOPWORDS:
            continue
        terms.append(cleaned)
    return terms


def _build_focus_context(documents: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for document in documents:
        title = _clean(document.get("title"))
        summary = _clean(document.get("summary"))
        for text, weight in ((title, 2), (summary, 1)):
            for term in _extract_terms_from_text(text):
                key = term.lower()
                counter[key] += weight
                if key not in first_seen:
                    first_seen[key] = len(first_seen)

    focus_terms = [
        term
        for term, _ in sorted(counter.items(), key=lambda item: (-item[1], first_seen[item[0]]))
    ][:4]
    pretty_terms = [term for term in focus_terms if term]
    topic = "、".join(pretty_terms[:2]) if len(pretty_terms) >= 2 else (pretty_terms[0] if pretty_terms else "核心主题")
    return {
        "focus_terms": pretty_terms,
        "topic": topic,
    }


class LessonPlanEntryCardsServiceV2:
    def __init__(
        self,
        *,
        summary_provider=None,
        recommendation_generator=None,
    ):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.recommendation_generator = recommendation_generator or LessonPlanEntryRecommendationGenerator()

    def get_cards(self, payload) -> dict[str, Any]:
        selected_doc_ids = _normalize_selected_doc_ids(getattr(payload, "selected_doc_ids", []))
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")

        owner = _clean(getattr(payload, "owner", "")) or None
        summary_result = self.summary_provider.get_selected_document_summaries(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(summary_result.get("documents") or [])
        focus_context = _build_focus_context(documents)
        topic = focus_context["topic"]

        preset_cards = self._build_preset_cards(topic=topic)
        recommendation_types = self._resolve_recommendation_types(
            selected_doc_ids=selected_doc_ids,
            topic=topic,
        )
        recommended_cards, generation_mode, generation_error = self._build_recommended_cards(
            documents=documents,
            recommendation_types=recommendation_types,
            topic=topic,
            fallback_used=bool(summary_result.get("fallback_used")),
        )
        default_selected_card_id = recommended_cards[0]["card_id"] if recommended_cards else preset_cards[0]["card_id"]

        result = {
            "entry_mode": "knowledge_base_lesson_plan",
            "default_selected_card_id": default_selected_card_id,
            "cards": [*preset_cards, *recommended_cards],
            "trace": {
                "selected_doc_count": len(selected_doc_ids),
                "summary_doc_count": len(documents),
                "fallback_used": bool(summary_result.get("fallback_used")),
                "recommendation_generation_mode": generation_mode,
            },
        }
        if generation_error:
            result["trace"]["recommendation_generation_error"] = generation_error
        return result

    def _build_preset_cards(self, *, topic: str) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for template in _PRESET_LIBRARY:
            cards.append(
                {
                    "card_id": template["card_id"],
                    "card_type": template["card_type"],
                    "title": template["title"],
                    "description": template["description"],
                    "prompt_draft": template["prompt_draft"],
                    "preset_key": template["preset_key"],
                    "prefill_config": {
                        "topic": topic,
                        "audience": "",
                        "duration": "45分钟",
                        "lesson_type": template["lesson_type"],
                        "objective": f"围绕{topic}完成{template['default_objective']}",
                        "style_hint": template["style_hint"],
                    },
                }
            )
        return cards

    def _resolve_recommendation_types(self, *, selected_doc_ids: list[str], topic: str) -> list[str]:
        normalized_topic = topic.lower()
        if any(marker in normalized_topic for marker in ("史", "人物", "朝代", "战役", "历史")):
            return ["historical_inquiry", "material_analysis", "review_summary"]
        if len(selected_doc_ids) >= 3:
            return ["review_summary", "knowledge_building", "practice_consolidation"]
        return ["knowledge_building", "practice_consolidation", "review_summary"]

    def _build_recommended_cards(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
        topic: str,
        fallback_used: bool,
    ) -> tuple[list[dict[str, Any]], str, str | None]:
        if fallback_used:
            return (
                self._build_rule_based_cards(
                    topic=topic,
                    recommendation_types=recommendation_types,
                ),
                "fallback_no_summary",
                None,
            )

        try:
            generated = self.recommendation_generator.generate_recommendations(
                documents=documents,
                recommendation_types=recommendation_types,
            )
            return self._build_cards_from_generated(generated=generated, topic=topic), "llm", None
        except Exception as exc:
            return (
                self._build_rule_based_cards(
                    topic=topic,
                    recommendation_types=recommendation_types,
                ),
                "fallback",
                str(exc),
            )

    def _build_cards_from_generated(
        self,
        *,
        generated: list[dict[str, Any]],
        topic: str,
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for index, item in enumerate(generated):
            recommendation_type = _clean(item.get("recommendation_type"))
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": _clean(item.get("title")),
                    "description": _clean(item.get("description")),
                    "prompt_draft": _clean(item.get("prompt_draft")),
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": _clean(item.get("fit_score"), "medium") or ("high" if index == 0 else "medium"),
                    "prefill_config": {
                        "topic": topic,
                        "audience": "",
                        "duration": "45分钟",
                        "lesson_type": _clean(item.get("lesson_type")),
                        "objective": _clean(item.get("objective")),
                        "style_hint": _clean(item.get("style_hint")),
                    },
                }
            )
        return cards

    def _build_rule_based_cards(self, *, topic: str, recommendation_types: list[str]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for index, recommendation_type in enumerate(recommendation_types):
            template = _RECOMMENDATION_LIBRARY[recommendation_type]
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": template["title"],
                    "description": template["description"],
                    "prompt_draft": template["prompt_draft"],
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high" if index == 0 else "medium",
                    "prefill_config": {
                        "topic": topic,
                        "audience": "",
                        "duration": "45分钟",
                        "lesson_type": template["lesson_type"],
                        "objective": f"围绕{topic}组织一节贴近真实课堂的单课时教案",
                        "style_hint": template["style_hint"],
                    },
                }
            )
        return cards


def build_default_lesson_plan_entry_cards_service_v2() -> LessonPlanEntryCardsServiceV2:
    return LessonPlanEntryCardsServiceV2(
        summary_provider=KnowledgeBaseSummaryProvider(),
        recommendation_generator=build_default_lesson_plan_entry_recommendation_generator(),
    )
