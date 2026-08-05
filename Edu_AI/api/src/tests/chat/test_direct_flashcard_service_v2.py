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
    def invoke(self, _messages):
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
