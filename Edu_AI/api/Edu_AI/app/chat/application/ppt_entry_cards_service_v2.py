from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
from app.chat.application.ppt_entry_recommendation_generator import (
    PptEntryRecommendationGenerator,
    build_default_ppt_entry_recommendation_generator,
)


_SUPPORTED_THEME_IDS = {"heu_academic_elegant", "heu_academic_basic"}
_LENGTH_TO_SLIDE_COUNT = {
    "short": 10,
    "medium": 16,
    "long": 24,
}
_FIT_SCORE_ORDER = {"high": 3, "medium": 2, "low": 1}


def _card_id_for_recommendation_type(recommendation_type: str) -> str:
    return f"rec-{recommendation_type.replace('_', '-')}"

_PRESET_LIBRARY = [
    {
        "card_id": "preset-knowledge-lecture",
        "card_type": "preset",
        "title": "Knowledge lecture",
        "description": "Best for concept explanation and classroom teaching.",
        "objective_hint": "课堂讲解",
        "length_option": "medium",
        "preset_key": "knowledge_lecture",
        "style_hint": "讲解清晰、结构稳定",
    },
    {
        "card_id": "preset-topic-briefing",
        "card_type": "preset",
        "title": "Topic briefing",
        "description": "Best for sharing a theme with a clear storyline.",
        "objective_hint": "主题分享",
        "length_option": "medium",
        "preset_key": "topic_briefing",
        "style_hint": "重点突出、逻辑顺畅",
    },
    {
        "card_id": "preset-comparison-analysis",
        "card_type": "preset",
        "title": "Comparison analysis",
        "description": "Best for comparing multiple sources or viewpoints.",
        "objective_hint": "对比分析",
        "length_option": "long",
        "preset_key": "comparison_analysis",
        "style_hint": "结构清晰、结论明确",
    },
    {
        "card_id": "preset-defense-summary",
        "card_type": "preset",
        "title": "Defense summary",
        "description": "Best for reporting, defense, and concise synthesis.",
        "objective_hint": "汇报答辩",
        "length_option": "short",
        "preset_key": "defense_summary",
        "style_hint": "结论先行、表达凝练",
    },
]

_RECOMMENDATION_LIBRARY = {
    "concept_focus": {
        "title": "Core concept focus",
        "description": "Highlight the foundational concepts and definitions in the selected material.",
        "objective_hint": "课堂讲解",
        "length_option": "medium",
        "theme_id": "heu_academic_basic",
        "style_hint": "先讲概念，再讲关系",
    },
    "process_flow": {
        "title": "Process flow explanation",
        "description": "Turn the material into a step-by-step flow deck with clear transitions.",
        "objective_hint": "流程讲解",
        "length_option": "medium",
        "theme_id": "heu_academic_elegant",
        "style_hint": "强调前后关系与步骤衔接",
    },
    "comparison_view": {
        "title": "Comparison view",
        "description": "Compare the key viewpoints, methods, or examples across the documents.",
        "objective_hint": "对比分析",
        "length_option": "long",
        "theme_id": "heu_academic_elegant",
        "style_hint": "先分类，再对比，最后下结论",
    },
    "case_application": {
        "title": "Case application",
        "description": "Use examples and scenarios to make the content easier to apply.",
        "objective_hint": "主题分享",
        "length_option": "medium",
        "theme_id": "heu_academic_elegant",
        "style_hint": "案例驱动，突出应用价值",
    },
}

_RULE_BASED_REC_TYPES = [
    "concept_focus",
    "process_flow",
    "comparison_view",
    "case_application",
]

_STOPWORDS = {
    "and",
    "the",
    "with",
    "from",
    "this",
    "that",
    "these",
    "those",
    "ppt",
    "presentation",
    "report",
    "summary",
    "document",
    "documents",
    "material",
    "materials",
    "selected",
    "core",
    "topic",
    "overview",
    "concept",
    "concepts",
    "flow",
    "process",
    "case",
    "cases",
}


def _clean_text(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_length_option(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"short", "medium", "long"} else "medium"


def _normalize_theme_id(value: object) -> str:
    text = str(value or "").strip()
    return text if text in _SUPPORTED_THEME_IDS else "heu_academic_elegant"


def _normalize_fit_score(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "medium"


def _normalize_key_points(values: list[object] | None, fallback: str) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        text = _clean_text(item)
        key = re.sub(r"\s+", "", text).lower()
        if not text or key in seen:
            continue
        points.append(text)
        seen.add(key)
    if not points:
        return [fallback]
    return points


def _length_to_slide_count(length_option: str) -> int:
    return _LENGTH_TO_SLIDE_COUNT.get(_normalize_length_option(length_option), 16)


def _extract_terms_from_text(text: str) -> list[str]:
    tokens = re.split(r"[\s,.;:!?，。；：、/\\|()（）\[\]{}<>]+", text or "")
    terms: list[str] = []
    for token in tokens:
        cleaned = _clean_text(token)
        key = cleaned.lower()
        if not cleaned or len(cleaned) < 2 or key in _STOPWORDS:
            continue
        terms.append(cleaned)
    return terms


def _build_focus_context(documents: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    first_seen: dict[str, int] = {}

    for document in documents:
        title = _clean_text(document.get("title"))
        summary = _clean_text(document.get("summary"))
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
    primary = focus_terms[0] if focus_terms else "core topic"
    secondary = focus_terms[1] if len(focus_terms) > 1 else primary
    tertiary = focus_terms[2] if len(focus_terms) > 2 else secondary

    if len(focus_terms) >= 2:
        topic_label = f"{focus_terms[0]} {focus_terms[1]}"
    else:
        topic_label = primary

    return {
        "focus_terms": focus_terms,
        "primary": primary,
        "secondary": secondary,
        "tertiary": tertiary,
        "topic_label": topic_label,
    }


def _build_prefill_config(
    *,
    topic_label: str,
    objective: str,
    length_option: str,
    theme_id: str,
    focus_terms: list[str],
    style_hint: str | None = None,
    deck_suffix: str = "PPT",
    audience: str = "general learners",
    general_requirements: str | None = None,
) -> dict[str, Any]:
    normalized_length = _normalize_length_option(length_option)
    slide_count = _length_to_slide_count(normalized_length)
    deck_title = f"{topic_label} {deck_suffix}".strip()
    return {
        "deck_title": deck_title,
        "deck_subtitle": f"For {audience}" if audience else None,
        "audience": audience,
        "objective": objective,
        "theme_id": _normalize_theme_id(theme_id),
        "length_option": normalized_length,
        "target_slide_count": slide_count,
        "key_points": _normalize_key_points(focus_terms, fallback=topic_label),
        "style_hint": style_hint,
        "special_requirements": None,
        "general_requirements": general_requirements or f"Auto-prefilled from selected documents for {objective}.",
    }


class PptEntryCardsServiceV2:
    def __init__(self, *, summary_provider=None, recommendation_generator=None):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.recommendation_generator = recommendation_generator or PptEntryRecommendationGenerator()

    def get_cards(self, payload) -> dict[str, Any]:
        selected_doc_ids = _normalize_selected_doc_ids(getattr(payload, "selected_doc_ids", []))
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")

        owner = _clean_text(getattr(payload, "owner", ""), default="") or None
        summary_result = self.summary_provider.get_selected_document_summaries(
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        documents = list(summary_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents summary is empty")

        focus_context = _build_focus_context(documents)
        if bool(summary_result.get("fallback_used")):
            recommended_cards = self._build_rule_based_cards(
                documents=documents,
                recommendation_types=_RULE_BASED_REC_TYPES,
                focus_context=focus_context,
            )
            generation_mode = "summary_fallback"
            generation_error = None
        else:
            try:
                generated = self.recommendation_generator.generate_recommendations(
                    documents=documents,
                    recommendation_types=_RULE_BASED_REC_TYPES,
                )
                recommended_cards = self._normalize_generated_cards(
                    generated=generated,
                    focus_context=focus_context,
                )
                generation_mode = _clean_text(
                    getattr(self.recommendation_generator, "last_generation_mode", ""),
                    "llm",
                )
                generation_error = _clean_text(
                    getattr(self.recommendation_generator, "last_generation_error", ""),
                ) or None
            except Exception as exc:
                recommended_cards = self._build_rule_based_cards(
                    documents=documents,
                    recommendation_types=_RULE_BASED_REC_TYPES,
                    focus_context=focus_context,
                )
                generation_mode = "rule_based"
                generation_error = str(exc)

        preset_cards = self._build_preset_cards(focus_context=focus_context)
        default_selected_card_id = self._pick_default_card_id(
            preset_cards=preset_cards,
            recommended_cards=recommended_cards,
        )
        result = {
            "entry_mode": "knowledge_base_ppt",
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

    def _pick_default_card_id(
        self,
        *,
        preset_cards: list[dict[str, Any]],
        recommended_cards: list[dict[str, Any]],
    ) -> str:
        if recommended_cards:
            best_card = max(
                enumerate(recommended_cards),
                key=lambda item: (
                    _FIT_SCORE_ORDER.get(_clean_text(item[1].get("fit_score"), "medium"), 2),
                    -item[0],
                ),
            )[1]
            best_card_id = str(best_card.get("card_id") or "").strip()
            if best_card_id:
                return best_card_id
            return str(preset_cards[0].get("card_id") or "") if preset_cards else ""
        if preset_cards:
            return str(preset_cards[0].get("card_id") or "").strip()
        return ""

    def _build_preset_cards(self, *, focus_context: dict[str, Any]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        topic_label = str(focus_context["topic_label"])
        focus_terms = list(focus_context["focus_terms"])
        for template in _PRESET_LIBRARY:
            objective = str(template["objective_hint"])
            length_option = str(template["length_option"])
            prefill_config = _build_prefill_config(
                topic_label=topic_label,
                objective=objective,
                length_option=length_option,
                theme_id="heu_academic_elegant",
                focus_terms=focus_terms,
                style_hint=str(template["style_hint"]),
                deck_suffix=str(template["title"]),
                general_requirements=f"Use this card as a preset for {objective}.",
            )
            cards.append(
                {
                    "card_id": template["card_id"],
                    "card_type": template["card_type"],
                    "title": template["title"],
                    "description": template["description"],
                    "objective_hint": objective,
                    "length_option": length_option,
                    "preset_key": template["preset_key"],
                    "style_hint": template["style_hint"],
                    "prefill_config": prefill_config,
                    "deck_title_hint": prefill_config["deck_title"],
                    "audience_hint": prefill_config["audience"],
                    "key_points_hint": list(prefill_config["key_points"]),
                }
            )
        return cards

    def _normalize_generated_cards(
        self,
        *,
        generated: list[dict[str, Any]],
        focus_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for index, item in enumerate(list(generated or [])):
            recommendation_type = _clean_text(item.get("recommendation_type"))
            if recommendation_type not in _RECOMMENDATION_LIBRARY:
                raise ValueError(f"unsupported_recommendation_type:{recommendation_type}")
            template = _RECOMMENDATION_LIBRARY[recommendation_type]
            raw_prefill = dict(item.get("prefill_config") or {})
            objective = _clean_text(raw_prefill.get("objective"), template["objective_hint"])
            length_option = _normalize_length_option(
                raw_prefill.get("length_option") or item.get("length_option") or template["length_option"]
            )
            theme_id = _normalize_theme_id(raw_prefill.get("theme_id") or template["theme_id"])
            topic_label = _clean_text(raw_prefill.get("deck_title"), focus_context["topic_label"])
            if topic_label.endswith("PPT"):
                topic_label = topic_label[:-3].strip()
            prefill_config = _build_prefill_config(
                topic_label=topic_label,
                objective=objective,
                length_option=length_option,
                theme_id=theme_id,
                focus_terms=list(raw_prefill.get("key_points") or focus_context["focus_terms"]),
                style_hint=_clean_text(raw_prefill.get("style_hint"), template["style_hint"]) or template["style_hint"],
                deck_suffix="PPT",
                audience=_clean_text(raw_prefill.get("audience"), "general learners"),
                general_requirements=_clean_text(
                    raw_prefill.get("general_requirements"),
                    f"Auto-prefilled from selected documents for {objective}.",
                ),
            )
            cards.append(
                {
                    "card_id": _card_id_for_recommendation_type(recommendation_type),
                    "card_type": "recommended",
                    "title": _clean_text(item.get("title"), template["title"]),
                    "description": _clean_text(item.get("description"), template["description"]),
                    "objective_hint": objective,
                    "length_option": length_option,
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": _normalize_fit_score(item.get("fit_score")),
                    "prefill_config": prefill_config,
                    "deck_title_hint": prefill_config["deck_title"],
                    "audience_hint": prefill_config["audience"],
                    "key_points_hint": list(prefill_config["key_points"]),
                    "style_hint": prefill_config["style_hint"],
                }
            )
        return cards

    def _build_rule_based_cards(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
        focus_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        focus_terms = list(focus_context["focus_terms"])
        topic_label = str(focus_context["topic_label"])
        for index, recommendation_type in enumerate(recommendation_types):
            template = dict(_RECOMMENDATION_LIBRARY[recommendation_type])
            if recommendation_type == "concept_focus":
                topic_suffix = "Concept focus"
            elif recommendation_type == "process_flow":
                topic_suffix = "Process flow"
            elif recommendation_type == "comparison_view":
                topic_suffix = "Comparison"
            else:
                topic_suffix = "Application"
            prefill_config = _build_prefill_config(
                topic_label=f"{topic_label} {topic_suffix}".strip(),
                objective=str(template["objective_hint"]),
                length_option=str(template["length_option"]),
                theme_id=str(template["theme_id"]),
                focus_terms=focus_terms,
                style_hint=str(template["style_hint"]),
                deck_suffix="PPT",
                general_requirements=(
                    f"Auto-generated fallback based on selected documents for {template['objective_hint']}."
                ),
            )
            cards.append(
                {
                    "card_id": _card_id_for_recommendation_type(recommendation_type),
                    "card_type": "recommended",
                    "title": template["title"],
                    "description": template["description"],
                    "objective_hint": template["objective_hint"],
                    "length_option": template["length_option"],
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high" if index < 2 else "medium",
                    "prefill_config": prefill_config,
                    "deck_title_hint": prefill_config["deck_title"],
                    "audience_hint": prefill_config["audience"],
                    "key_points_hint": list(prefill_config["key_points"]),
                    "style_hint": prefill_config["style_hint"],
                }
            )
        return cards


def _normalize_selected_doc_ids(values: list[str] | None) -> list[str]:
    return [
        _clean_text(item)
        for item in list(values or [])
        if _clean_text(item)
    ]


def build_default_ppt_entry_cards_service_v2() -> PptEntryCardsServiceV2:
    return PptEntryCardsServiceV2(
        summary_provider=KnowledgeBaseSummaryProvider(),
        recommendation_generator=build_default_ppt_entry_recommendation_generator(),
    )
