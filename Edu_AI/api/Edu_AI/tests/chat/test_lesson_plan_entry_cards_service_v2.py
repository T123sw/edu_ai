from types import SimpleNamespace

from app.chat.application.lesson_plan_entry_cards_service_v2 import LessonPlanEntryCardsServiceV2


class FakeSummaryProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_selected_document_summaries(self, *, selected_doc_ids, owner=None):
        self.calls.append((list(selected_doc_ids), owner))
        return self.result


class FakeRecommendationGenerator:
    def __init__(self, result=None, error=None):
        self.result = list(result or [])
        self.error = error
        self.calls = []

    def generate_recommendations(self, *, documents, recommendation_types):
        self.calls.append(
            {
                "documents": list(documents),
                "recommendation_types": list(recommendation_types),
            }
        )
        if self.error is not None:
            raise self.error
        return [dict(item) for item in self.result]


def test_lesson_plan_entry_cards_service_uses_realtime_generated_recommendations():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "关羽的战绩与历史评价",
                    "summary": "材料围绕关羽主要战役、历史评价和史料比较展开，适合组织史料探究。",
                    "summary_updated_at": "2026-04-15T10:00:00",
                }
            ],
            "summary_updated_at_snapshot": ["2026-04-15T10:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "historical_inquiry",
                "title": "关羽史料探究教案",
                "description": "围绕战绩与评价的史料辨析组织课堂探究。",
                "prompt_draft": "请围绕关羽战绩、历史评价与史料比较生成探究课教案。",
                "fit_score": "high",
                "lesson_type": "探究课",
                "objective": "通过史料比较形成人物评价",
                "style_hint": "突出史料对读、问题链和小组讨论",
            },
            {
                "recommendation_type": "material_analysis",
                "title": "关羽材料分析教案",
                "description": "围绕文本证据和批注任务组织课堂。",
                "prompt_draft": "请围绕关羽相关材料的证据提取与批注任务生成教案。",
                "fit_score": "medium",
                "lesson_type": "探究课",
                "objective": "通过材料圈点提炼关键信息",
                "style_hint": "突出材料批注和证据表达",
            },
            {
                "recommendation_type": "review_summary",
                "title": "关羽专题复习教案",
                "description": "围绕知识结构和历史评价回顾组织复习。",
                "prompt_draft": "请围绕关羽战绩与历史评价生成复习课教案。",
                "fit_score": "medium",
                "lesson_type": "复习课",
                "objective": "梳理战绩并完成人物评价回顾",
                "style_hint": "突出结构梳理和课堂检测",
            },
        ]
    )
    service = LessonPlanEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    recommended_cards = [card for card in result["cards"] if card["card_type"] == "recommended"]

    assert result["entry_mode"] == "knowledge_base_lesson_plan"
    assert result["trace"]["recommendation_generation_mode"] == "llm"
    assert recommended_cards[0]["title"] == "关羽史料探究教案"
    assert "关羽" in recommended_cards[0]["prompt_draft"]
    assert recommended_cards[0]["prefill_config"]["lesson_type"] == "探究课"
    assert recommended_cards[0]["prefill_config"]["objective"] == "通过史料比较形成人物评价"
    assert generator.calls[0]["recommendation_types"] == ["historical_inquiry", "material_analysis", "review_summary"]


def test_lesson_plan_entry_cards_service_calls_generator_on_every_request():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "快速排序的实现与优化",
                    "summary": "材料围绕数据结构、分区过程、递归实现和常见错误展开。",
                }
            ],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "knowledge_building",
                "title": "第一次知识建构教案",
                "description": "围绕快速排序核心概念组织新授。",
                "prompt_draft": "请围绕快速排序核心概念生成新授课教案。",
                "fit_score": "high",
                "lesson_type": "新授课",
                "objective": "理解快速排序核心过程",
                "style_hint": "突出过程拆解",
            },
            {
                "recommendation_type": "practice_consolidation",
                "title": "第一次练习巩固教案",
                "description": "围绕典型题和错因辨析组织讲评。",
                "prompt_draft": "请围绕快速排序典型错误生成讲评课教案。",
                "fit_score": "medium",
                "lesson_type": "讲评课",
                "objective": "识别常见错误并修正",
                "style_hint": "突出错因分析",
            },
            {
                "recommendation_type": "review_summary",
                "title": "第一次复习梳理教案",
                "description": "围绕知识结构回顾组织复习。",
                "prompt_draft": "请围绕快速排序的知识结构生成复习课教案。",
                "fit_score": "medium",
                "lesson_type": "复习课",
                "objective": "完成知识梳理",
                "style_hint": "突出结构回顾",
            },
        ]
    )
    service = LessonPlanEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)
    payload = SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester")

    first = service.get_cards(payload)
    generator.result[0]["title"] = "第二次知识建构教案"
    second = service.get_cards(payload)

    first_recommended = [card for card in first["cards"] if card["card_type"] == "recommended"]
    second_recommended = [card for card in second["cards"] if card["card_type"] == "recommended"]

    assert len(provider.calls) == 2
    assert len(generator.calls) == 2
    assert first_recommended[0]["title"] == "第一次知识建构教案"
    assert second_recommended[0]["title"] == "第二次知识建构教案"


def test_lesson_plan_entry_cards_service_falls_back_when_generator_fails():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "快速排序的实现与优化",
                    "summary": "材料围绕数据结构、分区过程、递归实现和常见错误展开。",
                }
            ],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(error=RuntimeError("llm unavailable"))
    service = LessonPlanEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    recommended_cards = [card for card in result["cards"] if card["card_type"] == "recommended"]

    assert result["trace"]["recommendation_generation_mode"] == "fallback"
    assert result["trace"]["recommendation_generation_error"] == "llm unavailable"
    assert recommended_cards
    assert all(card["prefill_config"]["topic"] for card in recommended_cards)
