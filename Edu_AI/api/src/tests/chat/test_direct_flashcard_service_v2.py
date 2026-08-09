from __future__ import annotations

from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_flashcard_service_v2 import (
    KnowledgeBaseDirectFlashcardServiceV2,
)


class _Provider:
    def get_selected_document_contents(self, *, selected_doc_ids, owner):
        assert selected_doc_ids == ["doc-1"]
        assert owner == "teacher-a"
        return {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "变量",
                    "summary": "变量用于保存可变化的数据。",
                    "content": "变量由名称、类型和值构成。",
                }
            ],
            "truncated": False,
        }


class _Llm:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(
            content=(
                '{"cards":['
                '{"front":"变量是什么？","back":"保存可变化数据的命名空间。","category":"概念","source_doc_id":"doc-1"},'
                '{"front":"变量包含哪些要素？","back":"名称、类型和值。","category":"结构","source_doc_id":"doc-1"},'
                '{"front":"变量的值是否固定？","back":"不是，它可以在程序运行中变化。","category":"特性","source_doc_id":"doc-1"}'
                "]}"
            )
        )


class _Storage:
    def __init__(self):
        self.saved = None

    def save_generated_material(self, **kwargs):
        self.saved = kwargs
        return True


class _NoSourceProvider:
    def get_selected_document_contents(self, **_kwargs):
        raise AssertionError("none source mode must not read the knowledge base")


def test_flashcard_generation_validates_and_persists_formal_resource():
    storage = _Storage()
    service = KnowledgeBaseDirectFlashcardServiceV2(
        content_provider=_Provider(),
        llm=_Llm(),
        course_storage_manager=storage,
    )
    result = service.generate(
        SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            selected_doc_ids=["doc-1"],
            flashcard_config={
                "title": "变量复习卡",
                "count": 3,
                "difficulty": "medium",
                "category": "概念",
                "show_sources": True,
            },
        ),
        job_id="job-1",
        config_snapshot_id="cfg-1",
    )
    artifact = result["artifacts"][0]
    assert artifact["artifact_type"] == "flashcard"
    assert artifact["content"]["cards"][0]["front"]
    assert artifact["content"]["cards"][0]["back"]
    assert artifact["content"]["count"] == 3
    assert storage.saved["material_type"] == "flashcard"
    assert storage.saved["owner_user_id"] == "teacher-a"
    assert storage.saved["source_job_id"] == "job-1"
    assert result["saved"] is True


def test_flashcard_generation_uses_title_when_documents_are_disabled():
    storage = _Storage()
    llm = _Llm()
    service = KnowledgeBaseDirectFlashcardServiceV2(
        content_provider=_NoSourceProvider(),
        llm=llm,
        course_storage_manager=storage,
    )

    result = service.generate(
        SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            source_mode="none",
            selected_doc_ids=[],
            flashcard_config={
                "title": "Variable review",
                "count": 3,
                "difficulty": "medium",
                "category": "concept",
                "show_sources": False,
            },
            research_context="Agent evidence: variables are mutable named storage.",
            research_bundle_id="bundle-1",
        ),
        job_id="job-none",
        config_snapshot_id="cfg-none",
    )

    assert result["artifacts"][0]["title"] == "Variable review"
    assert result["trace"]["selected_doc_count"] == 0
    assert "Agent evidence" in str(llm.messages[0])
    assert storage.saved["material_data"]["generation_state"]["research_context_used"] is True
