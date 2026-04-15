from app.chat.application.ppt_entry_cards_service_v2 import PptEntryCardsServiceV2
from app.chat.application.ppt_entry_recommendation_generator import PptEntryRecommendationGenerator


class DummySummaryProvider:
    def __init__(self, result):
        self.result = result

    def get_selected_document_summaries(self, *, selected_doc_ids, owner=None):
        return self.result


class DummyRecommendationGenerator:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.last_generation_mode = None
        self.last_generation_error = None

    def generate_recommendations(self, *, documents, recommendation_types):
        self.calls.append(
            {
                "documents": documents,
                "recommendation_types": recommendation_types,
            }
        )
        return self.result


def _make_ppt_card(
    *,
    card_id,
    recommendation_type,
    title,
    description,
    objective_hint,
    length_option,
    fit_score,
    theme_id="heu_academic_elegant",
):
    return {
        "card_id": card_id,
        "card_type": "recommended",
        "title": title,
        "description": description,
        "objective_hint": objective_hint,
        "length_option": length_option,
        "recommendation_type": recommendation_type,
        "recommendation_source": "doc_summaries",
        "fit_score": fit_score,
        "prefill_config": {
            "deck_title": "System skills",
            "audience": "undergraduate students",
            "objective": objective_hint,
            "theme_id": theme_id,
            "length_option": length_option,
            "target_slide_count": 16 if length_option == "medium" else 24,
            "key_points": ["definition", "workflow"],
            "style_hint": "clear and structured",
        },
    }


def test_ppt_entry_cards_service_returns_prefill_configs_and_default_selection():
    recommendation_generator = DummyRecommendationGenerator(
        [
            _make_ppt_card(
                card_id="rec-concept-focus",
                recommendation_type="concept_focus",
                title="Concept focus",
                description="Focus on concepts.",
                objective_hint="classroom teaching",
                length_option="medium",
                fit_score="medium",
            ),
            _make_ppt_card(
                card_id="rec-process-flow",
                recommendation_type="process_flow",
                title="Process flow explanation",
                description="Walk through the flow.",
                objective_hint="process explanation",
                length_option="medium",
                fit_score="high",
            ),
        ]
    )
    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider(
            {
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "title": "System skills",
                        "summary": "Introduces concepts, workflow, and examples.",
                    }
                ],
                "fallback_used": False,
            }
        ),
        recommendation_generator=recommendation_generator,
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["entry_mode"] == "knowledge_base_ppt"
    assert result["default_selected_card_id"] == "rec-process-flow"
    assert any(card["card_id"] == "preset-knowledge-lecture" for card in result["cards"])
    assert any(card["card_type"] == "recommended" for card in result["cards"])
    assert all("prefill_config" in card for card in result["cards"])
    assert recommendation_generator.calls[0]["recommendation_types"]


def test_ppt_entry_cards_service_uses_generator_trace_metadata():
    recommendation_generator = DummyRecommendationGenerator(
        [
            _make_ppt_card(
                card_id="rec-concept-focus",
                recommendation_type="concept_focus",
                title="Concept focus",
                description="Focus on concepts.",
                objective_hint="classroom teaching",
                length_option="medium",
                fit_score="high",
            )
        ]
    )
    recommendation_generator.last_generation_mode = "rule_based"
    recommendation_generator.last_generation_error = "structured output unavailable"
    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider(
            {
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "title": "System skills",
                        "summary": "Introduces concepts, workflow, and examples.",
                    }
                ],
                "fallback_used": False,
            }
        ),
        recommendation_generator=recommendation_generator,
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["trace"]["recommendation_generation_mode"] == "rule_based"
    assert result["trace"]["recommendation_generation_error"] == "structured output unavailable"


def test_ppt_entry_cards_service_fallback_path_still_returns_complete_prefill_configs():
    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider(
            {
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "title": "Process flow and application",
                        "summary": "This material emphasizes flow, mechanism, and cases.",
                    }
                ],
                "fallback_used": True,
            }
        ),
        recommendation_generator=DummyRecommendationGenerator([]),
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["default_selected_card_id"].startswith("rec-")
    assert all("prefill_config" in card for card in result["cards"])
    assert all(card["prefill_config"]["theme_id"] in {"heu_academic_elegant", "heu_academic_basic"} for card in result["cards"])


class DummyStructuredOutput:
    def __init__(self, bundle):
        self.bundle = bundle
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.bundle


class DummyLLM:
    def __init__(self, bundle):
        self.bundle = bundle
        self.prompts = []

    def with_structured_output(self, model, method="function_calling"):
        self.model = model
        self.method = method
        return DummyStructuredOutput(self.bundle)


class FailingLLM:
    def with_structured_output(self, model, method="function_calling"):
        raise RuntimeError("structured output unavailable")

    def invoke(self, prompt):
        raise RuntimeError("llm unavailable")


class StructuredFallbackLLM:
    def __init__(self, raw_payload):
        self.raw_payload = raw_payload
        self.prompts = []

    def with_structured_output(self, model, method="function_calling"):
        raise RuntimeError("structured output unavailable")

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("RawResponse", (), {"content": self.raw_payload})()


def test_ppt_entry_recommendation_generator_normalizes_structured_llm_output():
    generator = PptEntryRecommendationGenerator(
        llm=DummyLLM(
            {
                "cards": [
                    {
                        "recommendation_type": "comparison_view",
                        "title": "  Compare topics  ",
                        "description": "  Compare the source materials.  ",
                        "objective_hint": "  对比分析  ",
                        "length_option": "long",
                        "fit_score": "high",
                        "prefill_config": {
                            "deck_title": "  System skills  ",
                            "audience": "  undergraduate students  ",
                            "objective": "  对比分析  ",
                            "theme_id": "unsupported_theme",
                            "length_option": "long",
                            "target_slide_count": 24,
                            "key_points": [" A ", "B"],
                            "style_hint": "  concise  ",
                        },
                    }
                ]
            }
        )
    )

    result = generator.generate_recommendations(
        documents=[{"title": "System skills", "summary": "flow and examples"}],
        recommendation_types=["comparison_view"],
    )

    assert result[0]["title"] == "Compare topics"
    assert result[0]["prefill_config"]["theme_id"] == "heu_academic_elegant"
    assert result[0]["prefill_config"]["length_option"] == "long"
    assert generator.last_generation_mode == "llm"
    assert generator.last_generation_error is None


def test_ppt_entry_recommendation_generator_uses_raw_json_mode_when_structured_output_fails():
    generator = PptEntryRecommendationGenerator(
        llm=StructuredFallbackLLM(
            """
            {
                "cards": [
                    {
                        "recommendation_type": "comparison_view",
                        "title": "Compare topics",
                        "description": "Compare the source materials.",
                        "objective_hint": "瀵规瘮鍒嗘瀽",
                        "length_option": "long",
                        "fit_score": "high",
                        "prefill_config": {
                            "deck_title": "System skills",
                            "audience": "undergraduate students",
                            "objective": "瀵规瘮鍒嗘瀽",
                            "theme_id": "heu_academic_basic",
                            "length_option": "long",
                            "target_slide_count": 24,
                            "key_points": ["A", "B"],
                            "style_hint": "concise"
                        }
                    }
                ]
            }
            """
        )
    )

    result = generator.generate_recommendations(
        documents=[{"title": "System skills", "summary": "flow and examples"}],
        recommendation_types=["comparison_view"],
    )

    assert result[0]["title"] == "Compare topics"
    assert generator.last_generation_mode == "llm_raw_json"
    assert generator.last_generation_error == "structured output unavailable"


def test_ppt_entry_cards_service_reports_raw_json_generation_mode_when_structured_output_fails():
    recommendation_generator = DummyRecommendationGenerator(
        [
            _make_ppt_card(
                card_id="rec-concept-focus",
                recommendation_type="concept_focus",
                title="Concept focus",
                description="Focus on concepts.",
                objective_hint="classroom teaching",
                length_option="medium",
                fit_score="high",
            )
        ]
    )
    recommendation_generator.last_generation_mode = "llm_raw_json"
    recommendation_generator.last_generation_error = "structured output unavailable"
    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider(
            {
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "title": "System skills",
                        "summary": "Introduces concepts, workflow, and examples.",
                    }
                ],
                "fallback_used": False,
            }
        ),
        recommendation_generator=recommendation_generator,
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["trace"]["recommendation_generation_mode"] == "llm_raw_json"
    assert result["trace"]["recommendation_generation_error"] == "structured output unavailable"


def test_ppt_entry_recommendation_generator_falls_back_with_complete_prefill_config():
    generator = PptEntryRecommendationGenerator(llm=FailingLLM())

    result = generator.generate_recommendations(
        documents=[{"title": "Process flow", "summary": "flow, mechanism, and cases"}],
        recommendation_types=["process_flow", "concept_focus"],
    )

    assert len(result) == 2
    assert all(card["prefill_config"]["deck_title"] for card in result)
    assert all(card["prefill_config"]["theme_id"] in {"heu_academic_elegant", "heu_academic_basic"} for card in result)
    assert all(card["prefill_config"]["target_slide_count"] > 0 for card in result)
    assert generator.last_generation_mode == "rule_based"
    assert "llm unavailable" in (generator.last_generation_error or "")
