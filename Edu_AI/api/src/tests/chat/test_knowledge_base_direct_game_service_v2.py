from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.chat.application.knowledge_base_direct_game_service_v2 import KnowledgeBaseDirectGameServiceV2


class StubContentProvider:
    def get_selected_document_contents(self, *, selected_doc_ids, owner):
        return {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "中国古代政治制度",
                    "summary": "介绍分封制、郡县制和中央集权的制度演变。",
                    "content": "郡县制强调中央直接任命地方官员。分封制强调按宗法血缘分封诸侯。中央集权不断加强。",
                }
            ],
            "truncated": False,
        }


class StubLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(content=self.responses.pop(0))


class StubCourseStorageManager:
    def __init__(self):
        self.saved = []

    def save_generated_material(self, **kwargs):
        self.saved.append(kwargs)
        return True


class NoSourceContentProvider:
    def get_selected_document_contents(self, **_kwargs):
        raise AssertionError("none source mode must not read the knowledge base")


def _make_storage_root() -> Path:
    root = Path(__file__).resolve().parent / f"_mini_game_storage_{uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_direct_game_service_generates_drag_match_artifact():
    storage_root = _make_storage_root()
    storage_manager = StubCourseStorageManager()
    try:
        service = KnowledgeBaseDirectGameServiceV2(
            content_provider=StubContentProvider(),
            llm=StubLlm(
                [
                    '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制","right":"中央直接任免地方官的制度"},{"id":"p2","left":"分封制","right":"按宗法血缘分封诸侯的制度"}]}',
                ]
            ),
            course_storage_manager=storage_manager,
            storage_root=storage_root,
        )

        result = service.generate(
            SimpleNamespace(
                selected_doc_ids=["doc-1"],
                game_type="drag_match",
                course_id="course-1",
                scope_type="course",
                scope_id="course-1",
                owner="tester",
            )
        )

        artifact = result["artifacts"][0]
        html_path = storage_root / artifact["content"]["html_path"]

        assert result["action"]["name"] == "generate.game.direct"
        assert artifact["artifact_type"] == "game"
        assert artifact["content"]["template_id"] == "drag-match"
        assert artifact["content"]["game_data"]["pairs"][0]["right"] == "中央直接任免地方官的制度"
        assert artifact["content"]["html_url"].startswith("/api/chat/v2/games/html?path=")
        assert html_path.exists()
        assert storage_manager.saved[0]["material_type"] == "game"
    finally:
        rmtree(storage_root, ignore_errors=True)


def test_direct_game_service_retries_once_when_schema_validation_fails():
    storage_root = _make_storage_root()
    try:
        service = KnowledgeBaseDirectGameServiceV2(
            content_provider=StubContentProvider(),
            llm=StubLlm(
                [
                    '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制"}]}',
                    '{"title":"历史概念配对","pairs":[{"id":"p1","left":"郡县制","right":"中央直接任免地方官的制度"},{"id":"p2","left":"分封制","right":"按宗法血缘分封诸侯的制度"}]}',
                ]
            ),
            course_storage_manager=StubCourseStorageManager(),
            storage_root=storage_root,
        )

        result = service.generate(
            SimpleNamespace(
                selected_doc_ids=["doc-1"],
                game_type="drag_match",
                course_id="course-1",
                owner="tester",
            )
        )

        assert result["artifacts"][0]["content"]["game_data"]["pairs"][0]["right"] == "中央直接任免地方官的制度"
    finally:
        rmtree(storage_root, ignore_errors=True)


def test_direct_game_service_raises_after_second_invalid_payload():
    storage_root = _make_storage_root()
    try:
        service = KnowledgeBaseDirectGameServiceV2(
            content_provider=StubContentProvider(),
            llm=StubLlm(
                [
                    '{"title":"翻牌记忆","matches":[{"pair_id":"m1","card_a":"光合作用"}]}',
                    '{"title":"翻牌记忆","matches":[{"pair_id":"m1","card_a":"光合作用"}]}',
                ]
            ),
            course_storage_manager=StubCourseStorageManager(),
            storage_root=storage_root,
        )

        with pytest.raises(ValueError, match="game_generation_invalid_schema"):
            service.generate(
                SimpleNamespace(
                    selected_doc_ids=["doc-1"],
                    game_type="memory_flip",
                    course_id="course-1",
                    owner="tester",
                )
            )
    finally:
        rmtree(storage_root, ignore_errors=True)


def test_direct_game_service_generates_from_topic_without_documents():
    storage_root = _make_storage_root()
    llm = StubLlm(
        [
            '{"title":"Agent matching","pairs":[{"id":"p1","left":"Perception","right":"Observe the environment"},{"id":"p2","left":"Action","right":"Affect the environment"}]}'
        ]
    )
    try:
        service = KnowledgeBaseDirectGameServiceV2(
            content_provider=NoSourceContentProvider(),
            llm=llm,
            course_storage_manager=StubCourseStorageManager(),
            storage_root=storage_root,
        )

        result = service.generate(
            SimpleNamespace(
                selected_doc_ids=[],
                source_mode="none",
                game_type="drag_match",
                topic="Agent principles",
                card_count=12,
                difficulty="hard",
                duration_minutes=8,
                course_id="course-1",
                owner="tester",
            )
        )

        assert result["artifacts"][0]["artifact_type"] == "game"
        assert result["trace"]["selected_doc_count"] == 0
        assert "Agent principles" in str(llm.messages[0])
        assert "12" in str(llm.messages[0])
        assert "hard" in str(llm.messages[0])
        assert "8" in str(llm.messages[0])
    finally:
        rmtree(storage_root, ignore_errors=True)
