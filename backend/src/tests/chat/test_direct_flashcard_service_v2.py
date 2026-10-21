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


def test_supplemental_requirements_are_used_as_instructions_not_category():
    llm, storage = _Llm(), _Storage()
    service = KnowledgeBaseDirectFlashcardServiceV2(content_provider=_NoSourceProvider(), llm=llm, course_storage_manager=storage)
    service.generate(SimpleNamespace(owner='teacher-a', course_id='course-1', selected_doc_ids=[],
        flashcard_config={'title': '变量', 'count': 3, 'special_requirements': '对比赋值与复制，每张附例子'}),
        job_id='test-requirements', config_snapshot_id='test-config')
    prompt = llm.messages[0][1]['content']
    assert '补充要求：对比赋值与复制，每张附例子' in prompt
    assert '分类偏好：自动分类' in prompt
    assert all(card['category'] != '对比赋值与复制，每张附例子' for card in storage.saved['material_data']['content']['cards'])


def test_course_sources_are_preserved_only_when_enabled_and_grounded():
    import json
    for show_sources in (True, False):
        class CourseLlm:
            def invoke(self, messages):
                assert '当前知识点资料' in str(messages)
                return SimpleNamespace(content=json.dumps({'cards': [
                    {'front': str(i), 'back': '答案', 'source_doc_id': source}
                    for i, source in enumerate(['agent-research', 'invented', ''])
                ]}))
        storage = _Storage()
        service = KnowledgeBaseDirectFlashcardServiceV2(content_provider=_NoSourceProvider(), llm=CourseLlm(), course_storage_manager=storage)
        result = service.generate(SimpleNamespace(owner='teacher-a', course_id='course-1', selected_doc_ids=[],
            research_context='变量由名称、类型和值构成。',
            flashcard_config={'title': '变量', 'count': 3, 'show_sources': show_sources}),
            job_id='test-source', config_snapshot_id='test-config')
        cards = result['artifacts'][0]['content']['cards']
        assert cards[0]['source_title'] == ('当前知识点资料' if show_sources else None)
        assert cards[0]['source_doc_id'] == ('agent-research' if show_sources else None)
        assert all(card['source_title'] is None and card['source_doc_id'] is None for card in cards[1:])
