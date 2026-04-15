from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.utils.json_utils import extract_json_block

RecommendationType = Literal[
    "knowledge_building",
    "historical_inquiry",
    "practice_consolidation",
    "review_summary",
    "material_analysis",
]
FitScore = Literal["high", "medium", "low"]


class LessonPlanRecommendedCardDraft(BaseModel):
    recommendation_type: RecommendationType
    title: str
    description: str
    prompt_draft: str
    fit_score: FitScore = "medium"
    lesson_type: str
    objective: str
    style_hint: str


class LessonPlanRecommendedCardDraftBundle(BaseModel):
    cards: list[LessonPlanRecommendedCardDraft] = Field(default_factory=list)


class LessonPlanEntryRecommendationGenerator:
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

        try:
            structured = self.llm.with_structured_output(
                LessonPlanRecommendedCardDraftBundle,
                method="function_calling",
            )
            bundle = structured.invoke(prompt)
            return self._normalize_bundle(bundle=bundle, recommendation_types=recommendation_types)
        except Exception:
            raw = self.llm.invoke(prompt)
            payload = extract_json_block(getattr(raw, "content", raw))
            if not isinstance(payload, dict):
                raise
            bundle = LessonPlanRecommendedCardDraftBundle.model_validate(payload)
            return self._normalize_bundle(bundle=bundle, recommendation_types=recommendation_types)

    def _normalize_bundle(
        self,
        *,
        bundle: LessonPlanRecommendedCardDraftBundle,
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
                    "lesson_type": str(card.lesson_type or "").strip(),
                    "objective": str(card.objective or "").strip(),
                    "style_hint": str(card.style_hint or "").strip(),
                }
            )

        if any(
            not item["title"]
            or not item["description"]
            or not item["prompt_draft"]
            or not item["lesson_type"]
            or not item["objective"]
            or not item["style_hint"]
            for item in normalized
        ):
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
            "你是教师工作台里“创建教案”入口的推荐生成器。\n"
            "请基于当前勾选文档的标题和摘要，生成适合前端展示的系统推荐教案卡片。\n"
            "这些卡片不是最终教案，而是帮助教师快速选定一节课的组织方式与备课方向。\n\n"
            "输出要求:\n"
            "1. 只能依据给定文档标题和摘要，不要编造不存在的信息。\n"
            "2. 必须严格输出给定的 recommendation_type，每种类型输出一张卡片。\n"
            "3. 每张卡片必须包含 title、description、prompt_draft、fit_score、lesson_type、objective、style_hint。\n"
            "4. title 要自然、具体、像真实教师会点选的教案名称，不要出现 markdown、占位符或模板变量。\n"
            "5. description 要说明为什么这种教案更适合当前勾选材料。\n"
            "6. prompt_draft 必须是可直接用于后续教案生成的中文提示词，要强调只基于已选文档组织单课时教案，先生成大纲，再生成正文。\n"
            "7. lesson_type 要写成前端可直接预填的课型，如“新授课”“复习课”“探究课”“讲评课”。\n"
            "8. objective 要写成这节课的核心目标，贴近真实课堂，不要空泛。\n"
            "9. style_hint 要写成备课风格提示，例如“突出问题链与史料对读”“强调错因辨析与分层训练”。\n"
            "10. fit_score 只能是 high、medium、low。\n"
            "11. 保持 recommendation_type 原样，不要新增或删除类型。\n\n"
            f"需要输出的 recommendation_type 顺序: {json.dumps(list(recommendation_types), ensure_ascii=False)}\n\n"
            "当前文档摘要:\n"
            f"{chr(10).join(doc_lines)}"
        )


def build_default_lesson_plan_entry_recommendation_generator() -> LessonPlanEntryRecommendationGenerator:
    return LessonPlanEntryRecommendationGenerator(llm=get_fallback_llm())
