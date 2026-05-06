from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_ppt_outline_service_v2 import (
    KnowledgeBaseDirectPptOutlineServiceV2,
)
from app.chat.application.ppt_direct_draft_store import InMemoryPptDirectDraftStore
from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide


class DummySummaryProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_selected_document_summaries(self, *, selected_doc_ids, owner=None):
        self.calls.append((list(selected_doc_ids), owner))
        return self.result


class DummyOutlineBuilder:
    def __init__(self):
        self.calls = []

    def build(self, *, preparation):
        self.calls.append(preparation)
        return PptOutline(
            deck_title="Agent Basics",
            deck_subtitle="Classroom presentation",
            theme_id="heu_academic_elegant",
            slides=[
                PptOutlineSlide(
                    slide_index=1,
                    role="cover",
                    title="Agent Basics",
                    goal="Open the deck",
                    key_points=["Definition"],
                )
            ],
        )


def test_direct_ppt_outline_service_creates_draft_without_chat_context(monkeypatch):
    summary_provider = DummySummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "Agent Lecture",
                    "summary": "Introduces definitions and workflow structure.",
                }
            ],
            "fallback_used": False,
            "summary_updated_at_snapshot": ["2026-04-11T12:00:00"],
        }
    )
    outline_builder = DummyOutlineBuilder()
    store = InMemoryPptDirectDraftStore()
    monkeypatch.setattr(
        "app.chat.application.knowledge_base_direct_ppt_outline_service_v2.uuid4",
        lambda: SimpleNamespace(hex="abcdef1234567890"),
    )
    service = KnowledgeBaseDirectPptOutlineServiceV2(
        summary_provider=summary_provider,
        outline_builder=outline_builder,
        draft_store=store,
    )

    result = service.generate_outline(
        SimpleNamespace(
            course_id="course-1",
            scope_type="knowledge_point",
            scope_id="agent-basics",
            selected_doc_ids=["doc-1"],
            ppt_config={
                "deck_title": "Agent Basics",
                "audience": "Undergraduate students",
                "objective": "Classroom presentation",
                "theme_id": "heu_academic_elegant",
                "length_option": "medium",
                "target_slide_count": 16,
                "key_points": ["Definition"],
            },
            owner="tester",
        )
    )

    assert summary_provider.calls == [(["doc-1"], "tester")]
    assert result["action"]["name"] == "generate.ppt.outline.direct"
    assert result["draft"]["status"] == "outline_ready"
    assert result["trace"]["source_scope"] == "selected_documents_only"
    assert result["trace"]["uses_chat_context"] is False
    stored = store.get("ppt-draft-abcdef123456")
    assert stored["normalized_ppt_config"]["deck_title"] == "Agent Basics"
    assert stored["scope_type"] == "knowledge_point"
    assert stored["scope_id"] == "agent-basics"
    assert stored["selected_doc_snapshot_id"] == "snap-abcdef123456"
    assert outline_builder.calls[0].deck_topic == "Agent Basics"


def test_direct_ppt_outline_service_extracts_structured_config_from_general_requirements(monkeypatch):
    summary_provider = DummySummaryProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "Agent Lecture",
                    "summary": "Introduces definitions and workflow structure.",
                }
            ],
            "fallback_used": False,
            "summary_updated_at_snapshot": [],
        }
    )
    outline_builder = DummyOutlineBuilder()
    store = InMemoryPptDirectDraftStore()
    monkeypatch.setattr(
        "app.chat.application.knowledge_base_direct_ppt_outline_service_v2.uuid4",
        lambda: SimpleNamespace(hex="abcdef1234567890"),
    )
    service = KnowledgeBaseDirectPptOutlineServiceV2(
        summary_provider=summary_provider,
        outline_builder=outline_builder,
        draft_store=store,
    )

    service.generate_outline(
        SimpleNamespace(
            course_id="course-1",
            selected_doc_ids=["doc-1"],
            ppt_config={
                "deck_title": "Agent Basics",
                "audience": "",
                "objective": "",
                "theme_id": "heu_academic_elegant",
                "length_option": "short",
                "target_slide_count": 0,
                "key_points": [],
                "general_requirements": "受众为高中生，用于课堂讲解，做一份较长的PPT，重点突出定义、流程和案例。",
            },
            owner="tester",
        )
    )

    stored = store.get("ppt-draft-abcdef123456")
    assert stored["normalized_ppt_config"]["audience"] == "高中生"
    assert stored["normalized_ppt_config"]["objective"] == "课堂讲解"
    assert stored["normalized_ppt_config"]["length_option"] == "long"
    assert stored["normalized_ppt_config"]["target_slide_count"] == 24
    assert "定义" in stored["normalized_ppt_config"]["key_points"]


def test_direct_ppt_outline_service_requires_selected_docs():
    service = KnowledgeBaseDirectPptOutlineServiceV2(
        summary_provider=DummySummaryProvider({"documents": [], "fallback_used": True}),
        outline_builder=DummyOutlineBuilder(),
        draft_store=InMemoryPptDirectDraftStore(),
    )

    try:
        service.generate_outline(
            SimpleNamespace(
                selected_doc_ids=[],
                ppt_config={
                    "deck_title": "Agent Basics",
                    "audience": "Undergraduate students",
                    "objective": "Classroom presentation",
                    "theme_id": "heu_academic_elegant",
                    "target_slide_count": 16,
                    "key_points": ["Definition"],
                },
                owner="tester",
            )
        )
    except ValueError as exc:
        assert str(exc) == "selected_doc_ids is required"
    else:
        raise AssertionError("expected ValueError")
