from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.database import Base


@pytest.fixture
def engine(tmp_path: Path):
    value = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'conversation.db').as_posix()}")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def test_conversation_repository_round_trips_ordered_messages(engine):
    from app.persistence.postgres_conversation_repository import (
        PostgresConversationRepository,
    )

    repository = PostgresConversationRepository(engine)
    repository.upsert(
        {
            "conversation_id": "conv-1",
            "title": "Database chat",
            "owner": "teacher",
            "created_at": "2026-08-10T10:00:00+00:00",
            "updated_at": "2026-08-10T10:01:00+00:00",
            "state": {"course_id": "course-1", "scope_type": "course"},
            "messages": [
                {
                    "message_id": "msg-1",
                    "role": "user",
                    "content": "Question",
                    "timestamp": "2026-08-10T10:00:00+00:00",
                    "message_kind": "user_content",
                },
                {
                    "message_id": "msg-2",
                    "role": "assistant",
                    "content": "Answer",
                    "timestamp": "2026-08-10T10:01:00+00:00",
                    "message_kind": "assistant_content",
                    "sources": [{"title": "Source"}],
                },
            ],
        }
    )

    loaded = repository.get("conv-1")
    assert loaded["owner"] == "teacher"
    assert [item["message_id"] for item in loaded["messages"]] == ["msg-1", "msg-2"]
    assert loaded["messages"][1]["sources"] == [{"title": "Source"}]
    assert repository.list() == [loaded]
    assert repository.delete("conv-1") is True
    assert repository.get("conv-1") is None


def test_conversation_storage_uses_database_without_json_file(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from core.conversation_storage import ConversationStorage

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("CONVERSATION_PERSISTENCE_MODE", "postgres")
    json_path = tmp_path / "conversations.json"

    storage = ConversationStorage(storage_file=json_path)
    storage.ensure_conversation("conv-db", "First question", owner="teacher")
    storage.append_message("conv-db", "user", "First question")
    reloaded = ConversationStorage(storage_file=json_path)

    assert json_path.exists() is False
    assert reloaded.get_messages("conv-db")[0]["content"] == "First question"
    reloaded.delete_conversation("conv-db", owner="teacher")
    assert reloaded.list_conversations(owner="teacher")["total"] == 0
