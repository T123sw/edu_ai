from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.utils.json_utils import extract_json_block

RecommendationType = Literal[
    "summary",
    "comparison",
    "risk_analysis",
    "teaching_suggestion",
    "study_focus",
    "theme_outline",
]
FitScore = Literal["high", "medium", "low"]


class RecommendedCardDraft(BaseModel):
    recommendation_type: RecommendationType
    title: str
    description: str
    prompt_draft: str
    fit_score: FitScore = "medium"


class RecommendedCardDraftBundle(BaseModel):
    cards: list[RecommendedCardDraft] = Field(default_factory=list)


class ReportEntryRecommendationGenerator:
    def __init__(self, *, llm: Any | None = None):
        self.llm = llm or get_fallback_llm()

    def generate_recommendations(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
    ) -> list[dict[str, Any]]:
        if self.llm is None:
            raise RuntimeError("recommendation_llm_unavailable")
        if not documents:
            raise ValueError("documents is required")
        if not recommendation_types:
            raise ValueError("recommendation_types is required")

        prompt = self._build_prompt(
            documents=documents,
            recommendation_types=recommendation_types,
        )

        raw = self.llm.invoke(prompt)
        payload = extract_json_block(getattr(raw, "content", raw))
        if not isinstance(payload, dict):
            raise ValueError("invalid_recommendation_json")
        bundle = RecommendedCardDraftBundle.model_validate(payload)
        return self._normalize_bundle(bundle=bundle, recommendation_types=recommendation_types)

    def _normalize_bundle(
        self,
        *,
        bundle: RecommendedCardDraftBundle,
        recommendation_types: list[str],
    ) -> list[dict[str, Any]]:
        cards_by_type = {
            str(card.recommendation_type): card
            for card in list(bundle.cards or [])
        }
        normalized: list[dict[str, Any]] = []
        for recommendation_type in recommendation_types:
            card = cards_by_type.get(str(recommendation_type))
            if card is None:
                raise ValueError(f"missing_recommendation_type:{recommendation_type}")
            normalized.append(
                {
                    "recommendation_type": str(card.recommendation_type),
                    "title": str(card.title or "").strip(),
                    "description": str(card.description or "").strip(),
                    "prompt_draft": str(card.prompt_draft or "").strip(),
                    "fit_score": str(card.fit_score or "medium").strip() or "medium",
                }
            )

        if any(not item["title"] or not item["description"] or not item["prompt_draft"] for item in normalized):
            raise ValueError("empty_recommendation_fields")
        return normalized

    def _build_prompt(
        self,
        *,
        documents: list[dict[str, Any]],
        recommendation_types: list[str],
    ) -> str:
        doc_lines: list[str] = []
        for index, document in enumerate(documents, start=1):
            doc_lines.append(
                "\n".join(
                    [
                        f"文档{index}标题: {str(document.get('title') or '').strip()}",
                        f"文档{index}摘要: {str(document.get('summary') or '').strip()}",
                    ]
                )
            )

        return (
            "你是知识库报告入口的推荐生成器。"
            "请基于用户当前勾选文档的标题和摘要，为报告入口生成系统推荐卡片。"
            "这些卡片不是最终报告，而是帮助用户快速发起报告生成的方向建议。"
            "\n\n"
            "输出要求:\n"
            "1. 只使用给定文档标题和摘要，不要编造不存在的信息。\n"
            "2. 必须严格输出给定的 recommendation_type，每种类型输出一张卡片。\n"
            "3. 每张卡片都要包含 title、description、prompt_draft、fit_score。\n"
            "4. title 要自然、具体、中文表达，不要出现 markdown 标记、占位符、井号、星号或模板变量。\n"
            "5. description 要说明推荐方向为什么适合当前材料。\n"
            "6. prompt_draft 必须是可直接用于生成报告的中文提示词，要明确围绕哪些主题展开。\n"
            "7. fit_score 只能是 high、medium、low。\n"
            "8. 保持 recommendation_type 原样，不要新增或删除类型。\n"
            "9. Output only one valid JSON object. Do not use markdown fences or extra explanation.\n"
            '10. JSON shape: {"cards":[{"recommendation_type":"summary","title":"...","description":"...","prompt_draft":"...","fit_score":"high"}]}\n'
            "\n"
            f"需要输出的 recommendation_type 顺序: {json.dumps(list(recommendation_types), ensure_ascii=False)}\n\n"
            "当前文档摘要:\n"
            f"{chr(10).join(doc_lines)}"
        )


def build_default_report_entry_recommendation_generator() -> ReportEntryRecommendationGenerator:
    return ReportEntryRecommendationGenerator(llm=get_fallback_llm())
