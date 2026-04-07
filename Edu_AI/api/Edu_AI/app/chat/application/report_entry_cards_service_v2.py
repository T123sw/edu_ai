from __future__ import annotations

import re
from collections import Counter
from time import time
from typing import Any

from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider
from app.chat.application.report_entry_recommendation_generator import (
    ReportEntryRecommendationGenerator,
    build_default_report_entry_recommendation_generator,
)


def _build_preset_cards() -> list[dict[str, Any]]:
    return [
        {
            "card_id": "preset-brief",
            "card_type": "preset",
            "title": "简要报告",
            "description": "快速提炼材料主旨、关键结论与核心依据。",
            "prompt_draft": "请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中。",
            "preset_key": "brief",
        },
        {
            "card_id": "preset-detailed",
            "card_type": "preset",
            "title": "详细报告",
            "description": "完整梳理背景、分析过程、结论与建议。",
            "prompt_draft": "请基于已选文档，生成一份中文详细报告，包含背景、核心内容、重点分析、结论与建议，并尽可能完整覆盖材料中的主要信息。",
            "preset_key": "detailed",
        },
        {
            "card_id": "preset-study-plan",
            "card_type": "preset",
            "title": "学习方案",
            "description": "将材料整理成可执行的学习目标与学习路径。",
            "prompt_draft": "请基于已选文档，生成一份中文学习方案，包含学习目标、重点难点、学习顺序、阶段安排和实践任务，强调可执行性。",
            "preset_key": "study_plan",
        },
        {
            "card_id": "preset-custom",
            "card_type": "preset",
            "title": "自定义报告",
            "description": "保留自由表达空间，围绕你的补充要求生成报告。",
            "prompt_draft": "请基于已选文档，生成一份中文报告，并根据我后续补充的要求组织结构与内容，避免脱离文档空泛发挥。",
            "preset_key": "custom",
        },
    ]


_RECOMMENDATION_LIBRARY = {
    "summary": {
        "title": "核心内容总结",
        "description": "快速提炼材料中的核心主题与主要结论。",
        "prompt_draft": "请基于已选文档，生成一份中文总结报告，提炼核心主题、关键结论和主要依据，并用清晰结构呈现。",
    },
    "comparison": {
        "title": "关键观点对比",
        "description": "比较不同材料在核心观点和适用场景上的异同。",
        "prompt_draft": "请基于已选文档，生成一份中文对比分析报告，重点比较各材料在核心观点、方法路径、适用场景和局限性上的异同，并给出归纳结论。",
    },
    "risk_analysis": {
        "title": "问题与风险分析",
        "description": "识别材料中隐含的问题、风险与改进空间。",
        "prompt_draft": "请基于已选文档，生成一份中文问题与风险分析报告，识别关键问题、潜在风险、成因和可执行的改进建议。",
    },
    "teaching_suggestion": {
        "title": "教学应用建议",
        "description": "从材料中提炼适合课堂使用的教学启发。",
        "prompt_draft": "请基于已选文档，生成一份中文教学应用建议报告，提炼适合课堂实施的教学目标、活动设计、使用场景和注意事项。",
    },
    "study_focus": {
        "title": "学习重点提炼",
        "description": "提炼适合学生学习和复习的重点内容。",
        "prompt_draft": "请基于已选文档，生成一份中文学习重点提炼报告，概括核心知识点、常见难点和建议的学习顺序。",
    },
    "theme_outline": {
        "title": "主题结构梳理",
        "description": "梳理材料中的主题脉络和内容结构。",
        "prompt_draft": "请基于已选文档，生成一份中文主题结构梳理报告，梳理主要主题、层级关系和内容脉络，帮助快速建立整体认知。",
    },
}

_GENERIC_FALLBACK_TYPES = [
    "summary",
    "theme_outline",
    "study_focus",
    "teaching_suggestion",
]

_GENERIC_FALLBACK_OVERRIDES = {
    "teaching_suggestion": {
        "title": "应用建议整理",
        "description": "整理材料中的应用场景和可执行建议。",
        "prompt_draft": "请基于已选文档，生成一份中文应用建议整理报告，归纳适用场景、实践方式和可执行建议，帮助快速落地使用。",
    }
}

_FOCUS_TERM_SPLIT_PATTERN = re.compile(r"[，。；：、（）()\[\]【】《》\s,.;:!?！？]+")
_FOCUS_TERM_CONNECTOR_PATTERN = re.compile(
    r"(围绕|聚焦|强调|指出|提到|介绍|说明|梳理|提炼|分析|总结|归纳|适合|用于|输出|展开|关注|包括|包含|以及|并且|并|和|与|及)"
)
_FOCUS_TERM_PREFIX_PATTERN = re.compile(
    r"^(这份|本次|当前|相关|关于|围绕|聚焦|强调|指出|适合|需要|可以|用于|针对|对于|通过|基于|先|再|将)?"
    r"(第[一二三四五六七八九十]+份)?"
    r"(文档|材料|摘要|内容|报告)?"
)
_GENERIC_FOCUS_TERMS = {
    "文档",
    "材料",
    "摘要",
    "内容",
    "报告",
    "主题",
    "方向",
    "核心主题",
    "核心内容",
    "关键结论",
    "主要依据",
    "第一份材料",
    "第二份材料",
    "第一份",
    "第二份",
}


class ReportEntryCardsServiceV2:
    def __init__(
        self,
        *,
        summary_provider=None,
        recommendation_generator=None,
        now_fn=None,
        ttl_seconds: int = 0,
    ):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.recommendation_generator = recommendation_generator or ReportEntryRecommendationGenerator()
        self.now_fn = now_fn or time
        self.ttl_seconds = ttl_seconds

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

        recommendation_types = self._resolve_recommendation_types(
            summary_result=summary_result,
            selected_doc_ids=selected_doc_ids,
        )
        recommended_cards, generation_mode, generation_error = self._build_recommended_cards(
            summary_result=summary_result,
            recommendation_types=recommendation_types,
        )
        result = {
            "entry_mode": "knowledge_base_report",
            "cards": [*_build_preset_cards(), *recommended_cards],
            "trace": {
                "cache_hit": False,
                "selected_doc_count": len(selected_doc_ids),
                "summary_doc_count": len(list(summary_result.get("documents") or [])),
                "fallback_used": bool(summary_result.get("fallback_used")),
                "recommendation_generation_mode": generation_mode,
            },
        }
        if generation_error:
            result["trace"]["recommendation_generation_error"] = generation_error
        return result

    def _resolve_recommendation_types(
        self,
        *,
        summary_result: dict[str, Any],
        selected_doc_ids: list[str],
    ) -> list[str]:
        if bool(summary_result.get("fallback_used")):
            return list(_GENERIC_FALLBACK_TYPES)
        if len(selected_doc_ids) <= 1:
            return ["summary", "study_focus", "theme_outline", "teaching_suggestion"]
        return ["comparison", "risk_analysis", "teaching_suggestion", "summary"]

    def _build_recommended_cards(
        self,
        *,
        summary_result: dict[str, Any],
        recommendation_types: list[str],
    ) -> tuple[list[dict[str, Any]], str, str | None]:
        if bool(summary_result.get("fallback_used")):
            return self._build_cards_from_templates(
                recommendation_types=recommendation_types,
                fallback_used=True,
            ), "fallback_no_summary", None

        documents = list(summary_result.get("documents") or [])
        try:
            generated = self.recommendation_generator.generate_recommendations(
                documents=documents,
                recommendation_types=recommendation_types,
            )
            return self._build_cards_from_generated(generated=generated), "llm", None
        except Exception as exc:
            return (
                self._build_rule_based_cards(recommendation_types=recommendation_types, documents=documents),
                "fallback",
                str(exc),
            )

    def _build_cards_from_generated(self, *, generated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for index, item in enumerate(generated):
            recommendation_type = str(item.get("recommendation_type") or "").strip()
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": str(item.get("title") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "prompt_draft": str(item.get("prompt_draft") or "").strip(),
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": str(item.get("fit_score") or ("high" if index < 2 else "medium")).strip(),
                }
            )
        return cards

    def _build_cards_from_templates(
        self,
        *,
        recommendation_types: list[str],
        fallback_used: bool,
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for index, recommendation_type in enumerate(recommendation_types):
            template = dict(_RECOMMENDATION_LIBRARY[recommendation_type])
            if fallback_used and recommendation_type in _GENERIC_FALLBACK_OVERRIDES:
                template.update(_GENERIC_FALLBACK_OVERRIDES[recommendation_type])
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": template["title"],
                    "description": template["description"],
                    "prompt_draft": template["prompt_draft"],
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high" if index < 2 else "medium",
                }
            )
        return cards

    def _build_rule_based_cards(
        self,
        *,
        recommendation_types: list[str],
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        focus_context = self._build_focus_context(documents)
        cards: list[dict[str, Any]] = []
        for index, recommendation_type in enumerate(recommendation_types):
            template = self._build_dynamic_template(
                recommendation_type=recommendation_type,
                focus_context=focus_context,
            )
            cards.append(
                {
                    "card_id": f"rec-{recommendation_type}",
                    "card_type": "recommended",
                    "title": template["title"],
                    "description": template["description"],
                    "prompt_draft": template["prompt_draft"],
                    "recommendation_type": recommendation_type,
                    "recommendation_source": "doc_summaries",
                    "fit_score": "high" if index < 2 else "medium",
                }
            )
        return cards

    def _build_focus_context(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        counter: Counter[str] = Counter()
        first_seen: dict[str, int] = {}

        for document in documents:
            title = str(document.get("title") or "").strip()
            summary = str(document.get("summary") or "").strip()
            for text, weight in ((title, 2), (summary, 1)):
                for term in self._extract_focus_terms_from_text(text):
                    counter[term] += weight
                    if term not in first_seen:
                        first_seen[term] = len(first_seen)

        focus_terms = [
            term
            for term, _ in sorted(counter.items(), key=lambda item: (-item[1], first_seen[item[0]]))
        ][:4]
        primary = focus_terms[0] if focus_terms else "核心主题"
        secondary = focus_terms[1] if len(focus_terms) > 1 else primary
        tertiary = focus_terms[2] if len(focus_terms) > 2 else secondary

        return {
            "focus_terms": focus_terms,
            "primary": primary,
            "secondary": secondary,
            "tertiary": tertiary,
            "topic_pair": self._join_focus_terms(focus_terms[:2]),
            "topic_triplet": self._join_focus_terms(focus_terms[:3]),
        }

    def _extract_focus_terms_from_text(self, text: str) -> list[str]:
        normalized = _FOCUS_TERM_CONNECTOR_PATTERN.sub("|", text or "")
        normalized = _FOCUS_TERM_SPLIT_PATTERN.sub("|", normalized)

        terms: list[str] = []
        for raw_token in normalized.split("|"):
            cleaned = self._normalize_focus_term(raw_token)
            if cleaned:
                terms.append(cleaned)
        return terms

    def _normalize_focus_term(self, raw_token: str) -> str | None:
        token = str(raw_token or "").strip()
        if not token:
            return None

        token = _FOCUS_TERM_PREFIX_PATTERN.sub("", token).strip()
        token = token.strip("“”\"' ")
        if token.endswith("展开"):
            token = token[:-2].strip()
        if token.endswith("相关"):
            token = token[:-2].strip()

        if len(token) < 2 or len(token) > 10:
            return None
        if token in _GENERIC_FOCUS_TERMS:
            return None
        return token

    def _join_focus_terms(self, terms: list[str]) -> str:
        normalized_terms = [term for term in terms if term]
        if not normalized_terms:
            return "核心主题"
        if len(normalized_terms) == 1:
            return normalized_terms[0]
        if len(normalized_terms) == 2:
            return f"{normalized_terms[0]}与{normalized_terms[1]}"
        return "、".join(normalized_terms[:-1]) + f"与{normalized_terms[-1]}"

    def _build_dynamic_template(self, *, recommendation_type: str, focus_context: dict[str, Any]) -> dict[str, str]:
        focus_terms = list(focus_context["focus_terms"])
        primary = str(focus_context["primary"])
        topic_pair = str(focus_context["topic_pair"])
        topic_triplet = str(focus_context["topic_triplet"])
        topic_list = self._join_focus_terms(focus_terms)

        if recommendation_type == "summary":
            return {
                "title": f"{topic_pair}总结",
                "description": f"围绕{topic_list}快速提炼核心内容、主要结论与关键信息。",
                "prompt_draft": f"请基于已选文档，围绕{topic_list}生成一份中文总结报告，梳理核心主题、关键结论、主要依据，以及这些主题之间的关系。",
            }
        if recommendation_type == "comparison":
            return {
                "title": f"{topic_pair}对比",
                "description": f"比较已选材料在{topic_list}上的异同、侧重点与可参考结论。",
                "prompt_draft": f"请基于已选文档，围绕{topic_list}生成一份中文对比分析报告，重点比较不同材料在这些主题上的异同、差异来源和可参考结论。",
            }
        if recommendation_type == "risk_analysis":
            return {
                "title": f"{topic_pair}风险分析",
                "description": f"识别{topic_list}相关的关键风险、潜在问题与改进建议。",
                "prompt_draft": f"请基于已选文档，围绕{topic_list}生成一份中文风险分析报告，识别关键风险、潜在问题、成因以及可执行的改进建议。",
            }
        if recommendation_type == "teaching_suggestion":
            return {
                "title": f"{primary}教学建议",
                "description": f"结合{topic_list}整理可直接落地的教学建议与应用方向。",
                "prompt_draft": f"请基于已选文档，围绕{topic_list}生成一份中文教学建议报告，提炼适合教学应用的目标、活动设计、实施建议和注意事项。",
            }
        if recommendation_type == "study_focus":
            return {
                "title": f"{primary}学习重点",
                "description": f"提炼与{topic_list}相关的学习重点、难点与复习顺序。",
                "prompt_draft": f"请基于已选文档，围绕{topic_list}生成一份中文学习重点提炼报告，总结核心知识点、关键难点、学习顺序和复习建议。",
            }
        if recommendation_type == "theme_outline":
            return {
                "title": f"{primary}主题梳理",
                "description": f"梳理{topic_triplet}之间的主线关系与内容结构。",
                "prompt_draft": f"请基于已选文档，围绕{topic_triplet}生成一份中文主题结构梳理报告，说明主题层次、关联关系和整体脉络。",
            }
        return dict(_RECOMMENDATION_LIBRARY[recommendation_type])


def build_default_report_entry_cards_service_v2() -> ReportEntryCardsServiceV2:
    return ReportEntryCardsServiceV2(
        summary_provider=KnowledgeBaseSummaryProvider(),
        recommendation_generator=build_default_report_entry_recommendation_generator(),
    )
