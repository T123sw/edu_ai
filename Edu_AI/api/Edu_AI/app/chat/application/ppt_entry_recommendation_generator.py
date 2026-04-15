from __future__ import annotations

import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.agents.report_generation import get_fallback_llm, get_ppt_llm
from app.chat.api.schemas_v2 import PptEntryPrefillConfigV2
from app.chat.utils.json_utils import extract_json_block

PptRecommendationType = Literal["concept_focus", "process_flow", "comparison_view", "case_application"]
FitScore = Literal["high", "medium", "low"]

_SUPPORTED_THEMES = {"heu_academic_elegant", "heu_academic_basic"}
_LENGTH_TO_SLIDE_COUNT = {
    "short": 10,
    "medium": 16,
    "long": 24,
}
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

_LLM_RECOMMENDATION_LIBRARY = {
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


class RecommendedPptCardPrefillDraft(BaseModel):
    deck_title: str
    deck_subtitle: str | None = None
    audience: str = ""
    objective: str = ""
    theme_id: str = "heu_academic_elegant"
    length_option: str = "medium"
    target_slide_count: int = 0
    key_points: list[str] = Field(default_factory=list)
    style_hint: str | None = None
    special_requirements: str | None = None
    general_requirements: str | None = None


class RecommendedPptCardDraft(BaseModel):
    recommendation_type: PptRecommendationType
    title: str
    description: str
    objective_hint: str
    length_option: str = "medium"
    fit_score: FitScore = "medium"
    prefill_config: RecommendedPptCardPrefillDraft


class RecommendedPptCardDraftBundle(BaseModel):
    cards: list[RecommendedPptCardDraft] = Field(default_factory=list)


def _clean_text(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_length_option(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"short", "medium", "long"} else "medium"


def _normalize_theme_id(value: object) -> str:
    text = str(value or "").strip()
    return text if text in _SUPPORTED_THEMES else "heu_academic_elegant"


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
    topic_label = f"{focus_terms[0]} {focus_terms[1]}" if len(focus_terms) >= 2 else primary

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
    audience: str = "general learners",
    general_requirements: str | None = None,
) -> dict[str, Any]:
    normalized_length = _normalize_length_option(length_option)
    slide_count = _length_to_slide_count(normalized_length)
    return {
        "deck_title": f"{topic_label} PPT".strip(),
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


class PptEntryRecommendationGenerator:
    def __init__(self, *, llm: Any | None = None):
        self.llm = llm if llm is not None else (get_ppt_llm() or get_fallback_llm())
        self.last_generation_mode: str | None = None
        self.last_generation_error: str | None = None

    def _record_generation_state(self, *, mode: str, error: str | None = None) -> None:
        self.last_generation_mode = mode
        self.last_generation_error = error

    def generate_recommendations(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
    ) -> list[dict[str, Any]]:
        self.last_generation_mode = None
        self.last_generation_error = None
        if not recommendation_types:
            raise ValueError("recommendation_types is required")

        focus_context = _build_focus_context(documents)
        if self.llm is None:
            self._record_generation_state(mode="rule_based")
            return self._build_rule_based_cards(
                documents=documents,
                recommendation_types=recommendation_types,
                focus_context=focus_context,
            )

        prompt = self._build_prompt(
            documents=documents,
            recommendation_types=recommendation_types,
            focus_context=focus_context,
        )

        try:
            structured = self.llm.with_structured_output(RecommendedPptCardDraftBundle, method="function_calling")
            bundle = structured.invoke(prompt)
            self._record_generation_state(mode="llm")
            return self._normalize_bundle(
                bundle=bundle,
                recommendation_types=recommendation_types,
                focus_context=focus_context,
            )
        except Exception as structured_error:
            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if not isinstance(payload, dict):
                    raise ValueError("invalid_recommendation_payload")
                bundle = RecommendedPptCardDraftBundle.model_validate(payload)
                self._record_generation_state(mode="llm_raw_json", error=str(structured_error) or None)
                return self._normalize_bundle(
                    bundle=bundle,
                    recommendation_types=recommendation_types,
                    focus_context=focus_context,
                )
            except Exception as raw_error:
                self._record_generation_state(
                    mode="rule_based",
                    error=str(raw_error) or str(structured_error) or None,
                )
                return self._build_rule_based_cards(
                    documents=documents,
                    recommendation_types=recommendation_types,
                    focus_context=focus_context,
                )

    def _normalize_bundle(
        self,
        *,
        bundle: Any,
        recommendation_types: list[str],
        focus_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(bundle, RecommendedPptCardDraftBundle):
            bundle = RecommendedPptCardDraftBundle.model_validate(bundle)

        cards_by_type = {str(card.recommendation_type): card for card in list(bundle.cards or [])}
        normalized: list[dict[str, Any]] = []
        for recommendation_type in recommendation_types:
            card = cards_by_type.get(str(recommendation_type))
            if card is None:
                raise ValueError(f"missing_recommendation_type:{recommendation_type}")
            template = _LLM_RECOMMENDATION_LIBRARY[str(recommendation_type)]
            prefill = card.prefill_config.model_dump()
            objective = _clean_text(prefill.get("objective"), card.objective_hint or template["objective_hint"])
            length_option = _normalize_length_option(prefill.get("length_option") or card.length_option or template["length_option"])
            topic_label = _clean_text(prefill.get("deck_title"), focus_context["topic_label"])
            if topic_label.endswith("PPT"):
                topic_label = topic_label[:-3].strip()
            normalized_prefill = _build_prefill_config(
                topic_label=topic_label,
                objective=objective,
                length_option=length_option,
                theme_id=_normalize_theme_id(prefill.get("theme_id") or template["theme_id"]),
                focus_terms=list(prefill.get("key_points") or focus_context["focus_terms"]),
                style_hint=_clean_text(prefill.get("style_hint"), template["style_hint"]) or template["style_hint"],
                audience=_clean_text(prefill.get("audience"), "general learners"),
                general_requirements=_clean_text(
                    prefill.get("general_requirements"),
                    f"Auto-prefilled from selected documents for {objective}.",
                ),
            )
            normalized.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": _clean_text(card.title, template["title"]),
                    "description": _clean_text(card.description, template["description"]),
                    "objective_hint": objective,
                    "length_option": length_option,
                    "recommendation_type": str(card.recommendation_type),
                    "recommendation_source": "doc_summaries",
                    "fit_score": _normalize_fit_score(card.fit_score),
                    "prefill_config": normalized_prefill,
                    "deck_title_hint": normalized_prefill["deck_title"],
                    "audience_hint": normalized_prefill["audience"],
                    "key_points_hint": list(normalized_prefill["key_points"]),
                    "style_hint": normalized_prefill["style_hint"],
                }
            )

        if any(
            not item["title"] or not item["description"] or not item["objective_hint"] or not item["prefill_config"]["deck_title"]
            for item in normalized
        ):
            raise ValueError("empty_recommendation_fields")
        return normalized

    def _build_rule_based_cards(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
        focus_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        topic_label = str(focus_context["topic_label"])
        focus_terms = list(focus_context["focus_terms"])
        for index, recommendation_type in enumerate(recommendation_types):
            template = _LLM_RECOMMENDATION_LIBRARY[str(recommendation_type)]
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
                general_requirements=(
                    f"Auto-generated fallback based on selected documents for {template['objective_hint']}."
                ),
            )
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
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

    def _build_prompt(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
        focus_context: dict[str, Any],
    ) -> str:
        doc_lines: list[str] = []
        for index, document in enumerate(documents, start=1):
            doc_lines.append(
                "\n".join(
                    [
                        f"doc_{index}_title: {_clean_text(document.get('title'))}",
                        f"doc_{index}_summary: {_clean_text(document.get('summary'))}",
                    ]
                )
            )

        return (
            "You are a PPT entry recommendation generator.\n"
            "Return JSON only that matches the RecommendedPptCardDraftBundle schema.\n"
            "Every recommendation_type must appear exactly once in the same order as requested.\n"
            "Every card must include title, description, objective_hint, length_option, fit_score, and prefill_config.\n"
            "prefill_config must include deck_title, audience, objective, theme_id, length_option, target_slide_count, key_points, style_hint, special_requirements, and general_requirements.\n"
            "Allowed theme_id values are heu_academic_elegant and heu_academic_basic.\n"
            "Allowed length_option values are short, medium, and long.\n"
            f"Requested recommendation types: {recommendation_types}\n"
            f"Focus topic: {focus_context['topic_label']}\n"
            + "\n".join(doc_lines)
        )


def build_default_ppt_entry_recommendation_generator() -> PptEntryRecommendationGenerator:
    return PptEntryRecommendationGenerator(llm=get_ppt_llm() or get_fallback_llm())
