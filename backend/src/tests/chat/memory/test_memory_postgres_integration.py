from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, inspect

from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.service import AgentMemoryService
from app.chat.memory.settings import AgentMemorySettings
from app.database import (
    AgentMemoryAuditEvent,
    AgentMemoryItem,
    ConversationEpisode,
    UserProfileFact,
    database_session,
)


@pytest.mark.integration
def test_postgres_memory_write_and_cross_conversation_recall() -> None:
    database_url = os.getenv("AGENT_MEMORY_TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("AGENT_MEMORY_TEST_DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    required_tables = {
        "agent_memory_items",
        "user_profile_facts",
        "conversation_episodes",
        "agent_memory_audit_events",
    }
    assert required_tables <= set(inspect(engine).get_table_names())

    subject = f"memory-probe-{uuid4().hex}"
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=False,
        embedding_enabled=False,
    )
    service = AgentMemoryService(
        repository=SqlAlchemyMemoryRepository(engine),
        settings=settings,
        langmem_adapter=LangMemAdapter(settings=settings),
    )
    try:
        write = service.persist_turn(
            actor={"user_id": subject, "role": "student"},
            conversation_id="postgres-probe-write",
            course_id="course-probe",
            user_message="我更喜欢用生活中的例子来理解抽象概念",
            assistant_message="好的。",
            agent_state={},
            tool_events=[],
        )
        context = service.read_for_agent(
            actor={"user_id": subject, "role": "student"},
            conversation_id="postgres-probe-read",
            course_id="course-probe",
            task_id=None,
            query="请解释递归",
            token_budget=800,
        )

        assert write.written_count == 1
        assert context.profile_facts
        assert "生活" in context.profile_facts[0].value
    finally:
        with database_session(engine=engine) as session:
            session.execute(
                delete(AgentMemoryAuditEvent).where(
                    AgentMemoryAuditEvent.subject_user_id == subject
                )
            )
            session.execute(
                delete(UserProfileFact).where(
                    UserProfileFact.subject_user_id == subject
                )
            )
            session.execute(
                delete(AgentMemoryItem).where(
                    AgentMemoryItem.subject_user_id == subject
                )
            )
            session.execute(
                delete(ConversationEpisode).where(
                    ConversationEpisode.owner_user_id == subject
                )
            )
        engine.dispose()
