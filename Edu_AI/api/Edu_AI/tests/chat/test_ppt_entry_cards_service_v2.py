from app.chat.application.ppt_entry_cards_service_v2 import PptEntryCardsServiceV2


class DummySummaryProvider:
    def __init__(self, result):
        self.result = result

    def get_selected_document_summaries(self, *, selected_doc_ids, owner=None):
        return self.result


def test_ppt_entry_cards_service_returns_ppt_specific_presets_and_recommendations():
    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider(
            {
                "documents": [
                    {
                        "doc_id": "doc-1",
                        "title": "智能体工作流",
                        "summary": "介绍概念定义、执行流程和典型应用案例。",
                    }
                ],
                "fallback_used": False,
            }
        )
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["entry_mode"] == "knowledge_base_ppt"
    assert any(card["card_id"] == "preset-knowledge-lecture" for card in result["cards"])
    assert any(card["card_type"] == "recommended" for card in result["cards"])
    assert all("prompt_draft" not in card for card in result["cards"])
