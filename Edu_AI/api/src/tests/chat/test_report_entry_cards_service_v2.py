from types import SimpleNamespace

from app.chat.application.report_entry_cards_service_v2 import ReportEntryCardsServiceV2


class FakeSummaryProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_selected_document_summaries(self, *, selected_doc_ids, owner):
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


def test_report_entry_cards_service_returns_preset_cards_first():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "单文档",
                    "summary": "这是一份关于课堂观察的文档摘要。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                }
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "summary",
                "title": "课堂观察总结",
                "description": "总结课堂观察要点",
                "prompt_draft": "请围绕课堂观察生成总结报告",
                "fit_score": "high",
            },
            {
                "recommendation_type": "study_focus",
                "title": "学习重点",
                "description": "提炼学习重点",
                "prompt_draft": "请提炼学习重点",
                "fit_score": "high",
            },
            {
                "recommendation_type": "theme_outline",
                "title": "主题梳理",
                "description": "梳理主题结构",
                "prompt_draft": "请梳理主题结构",
                "fit_score": "medium",
            },
            {
                "recommendation_type": "teaching_suggestion",
                "title": "教学建议",
                "description": "输出教学建议",
                "prompt_draft": "请整理教学建议",
                "fit_score": "medium",
            },
        ]
    )
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(
        SimpleNamespace(
            selected_doc_ids=["doc-1"],
            course_id="course-1",
            owner="tester",
        )
    )

    assert result["entry_mode"] == "knowledge_base_report"
    assert [card["card_id"] for card in result["cards"][:4]] == [
        "preset-brief",
        "preset-detailed",
        "preset-study-plan",
        "preset-custom",
    ]


def test_report_entry_cards_service_prefers_single_document_intents():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "单文档",
                    "summary": "材料主要介绍学习重点、知识结构与教学建议。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                }
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "summary",
                "title": "课堂观察总结",
                "description": "总结课堂观察要点",
                "prompt_draft": "请围绕课堂观察生成总结报告",
                "fit_score": "high",
            },
            {
                "recommendation_type": "study_focus",
                "title": "学习重点",
                "description": "提炼学习重点",
                "prompt_draft": "请提炼学习重点",
                "fit_score": "high",
            },
            {
                "recommendation_type": "theme_outline",
                "title": "主题梳理",
                "description": "梳理主题结构",
                "prompt_draft": "请梳理主题结构",
                "fit_score": "medium",
            },
            {
                "recommendation_type": "teaching_suggestion",
                "title": "教学建议",
                "description": "输出教学建议",
                "prompt_draft": "请整理教学建议",
                "fit_score": "medium",
            },
        ]
    )
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    recommendation_types = [card["recommendation_type"] for card in result["cards"][4:]]

    assert recommendation_types == [
        "summary",
        "study_focus",
        "theme_outline",
        "teaching_suggestion",
    ]
    assert generator.calls[0]["recommendation_types"] == recommendation_types


def test_report_entry_cards_service_uses_realtime_generated_recommendations():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "课堂观察记录",
                    "summary": "文档围绕课堂观察、学习重点、教学建议和学生互动展开。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                }
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "summary",
                "title": "课堂观察与学习重点总结",
                "description": "围绕课堂观察和学习重点生成总结",
                "prompt_draft": "请围绕课堂观察、学习重点与教学建议生成总结报告",
                "fit_score": "high",
            },
            {
                "recommendation_type": "study_focus",
                "title": "课堂观察学习重点",
                "description": "提炼课堂观察相关学习重点",
                "prompt_draft": "请提炼课堂观察中的学习重点",
                "fit_score": "high",
            },
            {
                "recommendation_type": "theme_outline",
                "title": "课堂观察主题脉络",
                "description": "梳理课堂观察主题",
                "prompt_draft": "请梳理课堂观察主题结构",
                "fit_score": "medium",
            },
            {
                "recommendation_type": "teaching_suggestion",
                "title": "课堂观察教学建议",
                "description": "结合课堂观察输出教学建议",
                "prompt_draft": "请围绕课堂观察给出教学建议",
                "fit_score": "medium",
            },
        ]
    )
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    recommended_cards = result["cards"][4:]
    summary_card = next(card for card in recommended_cards if card["recommendation_type"] == "summary")
    teaching_card = next(card for card in recommended_cards if card["recommendation_type"] == "teaching_suggestion")

    assert "课堂观察" in summary_card["title"]
    assert "学习重点" in summary_card["prompt_draft"]
    assert "教学建议" in teaching_card["description"]
    assert "课堂观察" in teaching_card["prompt_draft"]
    assert result["trace"]["cache_hit"] is False
    assert result["trace"]["recommendation_generation_mode"] == "llm"


def test_report_entry_cards_service_prefers_multi_document_intents():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "文档一",
                    "summary": "第一份材料强调方法与课堂表现。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                },
                {
                    "doc_id": "doc-2",
                    "title": "文档二",
                    "summary": "第二份材料强调差异、风险和教学启发。",
                    "summary_updated_at": "2026-04-07T11:00:00",
                },
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00", "2026-04-07T11:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "comparison",
                "title": "课堂表现对比",
                "description": "比较课堂表现差异",
                "prompt_draft": "请比较课堂表现差异",
                "fit_score": "high",
            },
            {
                "recommendation_type": "risk_analysis",
                "title": "课堂表现风险分析",
                "description": "识别课堂表现风险",
                "prompt_draft": "请分析课堂表现风险",
                "fit_score": "high",
            },
            {
                "recommendation_type": "teaching_suggestion",
                "title": "课堂表现教学建议",
                "description": "输出教学建议",
                "prompt_draft": "请给出教学建议",
                "fit_score": "medium",
            },
            {
                "recommendation_type": "summary",
                "title": "课堂表现总结",
                "description": "总结课堂表现",
                "prompt_draft": "请总结课堂表现",
                "fit_score": "medium",
            },
        ]
    )
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1", "doc-2"], owner="tester"))
    recommendation_types = [card["recommendation_type"] for card in result["cards"][4:]]

    assert recommendation_types == [
        "comparison",
        "risk_analysis",
        "teaching_suggestion",
        "summary",
    ]
    assert generator.calls[0]["recommendation_types"] == recommendation_types


def test_report_entry_cards_service_calls_generator_on_every_request():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "课堂表现分析",
                    "summary": "第一份材料强调课堂表现、学生参与和学习重点。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                },
                {
                    "doc_id": "doc-2",
                    "title": "教学改进建议",
                    "summary": "第二份材料强调差异、风险、教学建议和改进方向。",
                    "summary_updated_at": "2026-04-07T11:00:00",
                },
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00", "2026-04-07T11:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(
        result=[
            {
                "recommendation_type": "comparison",
                "title": "第1次课堂表现对比",
                "description": "比较课堂表现差异",
                "prompt_draft": "请比较课堂表现差异",
                "fit_score": "high",
            },
            {
                "recommendation_type": "risk_analysis",
                "title": "第1次课堂风险分析",
                "description": "识别课堂风险",
                "prompt_draft": "请分析课堂风险",
                "fit_score": "high",
            },
            {
                "recommendation_type": "teaching_suggestion",
                "title": "第1次教学建议",
                "description": "输出教学建议",
                "prompt_draft": "请输出教学建议",
                "fit_score": "medium",
            },
            {
                "recommendation_type": "summary",
                "title": "第1次课堂总结",
                "description": "总结课堂重点",
                "prompt_draft": "请总结课堂重点",
                "fit_score": "medium",
            },
        ]
    )
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)
    payload = SimpleNamespace(selected_doc_ids=["doc-1", "doc-2"], owner="tester")

    first = service.get_cards(payload)
    generator.result[0]["title"] = "第2次课堂表现对比"
    second = service.get_cards(payload)

    assert len(provider.calls) == 2
    assert len(generator.calls) == 2
    assert first["trace"]["cache_hit"] is False
    assert second["trace"]["cache_hit"] is False
    assert first["cards"][4]["title"] == "第1次课堂表现对比"
    assert second["cards"][4]["title"] == "第2次课堂表现对比"


def test_report_entry_cards_service_falls_back_when_generator_fails():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "课堂观察记录",
                    "summary": "文档围绕课堂观察、学习重点、教学建议和学生互动展开。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                }
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(error=RuntimeError("llm failed"))
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    summary_card = next(card for card in result["cards"][4:] if card["recommendation_type"] == "summary")

    assert len(generator.calls) == 1
    assert result["trace"]["recommendation_generation_mode"] == "fallback"
    assert "课堂观察" in summary_card["title"]


def test_report_entry_cards_service_rule_fallback_filters_markdown_noise():
    provider = FakeSummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "## **随机过程与$t$**",
                    "summary": "材料围绕##、** 随机过程与$t$、马尔可夫链和泊松过程展开。",
                    "summary_updated_at": "2026-04-07T10:00:00",
                },
                {
                    "doc_id": "doc-2",
                    "title": "# 随机过程案例",
                    "summary": "重点比较状态转移、平稳分布与实际建模案例。",
                    "summary_updated_at": "2026-04-07T11:00:00",
                },
            ],
            "summary_updated_at_snapshot": ["2026-04-07T10:00:00", "2026-04-07T11:00:00"],
            "fallback_used": False,
        }
    )
    generator = FakeRecommendationGenerator(error=RuntimeError("llm failed"))
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1", "doc-2"], owner="tester"))
    recommended_cards = result["cards"][4:]
    rendered_text = "\n".join(
        f"{card['title']}\n{card['description']}\n{card['prompt_draft']}"
        for card in recommended_cards
    )

    assert "随机过程" in rendered_text
    assert "##" not in rendered_text
    assert "**" not in rendered_text
    assert "$t$" not in rendered_text


def test_report_entry_cards_service_returns_generic_fallback_when_all_summaries_missing():
    provider = FakeSummaryProvider(
        {
            "documents": [],
            "summary_updated_at_snapshot": [],
            "fallback_used": True,
        }
    )
    generator = FakeRecommendationGenerator()
    service = ReportEntryCardsServiceV2(summary_provider=provider, recommendation_generator=generator)

    result = service.get_cards(SimpleNamespace(selected_doc_ids=["doc-1"], owner="tester"))
    recommended_titles = [card["title"] for card in result["cards"][4:]]

    assert recommended_titles == [
        "核心内容总结",
        "主题结构梳理",
        "学习重点提炼",
        "应用建议整理",
    ]
    assert result["trace"]["fallback_used"] is True
    assert len(generator.calls) == 0
