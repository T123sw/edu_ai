from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete

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
from core.config import Config


@pytest.mark.live_integration
def test_live_langmem_extracts_persists_and_recalls_in_postgres() -> None:
    database_url = os.getenv("AGENT_MEMORY_TEST_DATABASE_URL", "").strip()
    if os.getenv("AGENT_MEMORY_RUN_LIVE_LANGMEM", "").strip() != "1":
        pytest.skip("AGENT_MEMORY_RUN_LIVE_LANGMEM is not enabled")
    if not database_url or not Config.DEEP_MODEL_API_KEY:
        pytest.skip("database or model provider is not configured")

    engine = create_engine(database_url, pool_pre_ping=True)
    subject = f"langmem-live-{uuid4().hex}"
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=True,
        langmem_background=False,
        langmem_timeout_ms=30_000,
        langmem_max_candidates=3,
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
            conversation_id="langmem-live-write",
            course_id="course-probe",
            user_message="以后请叫我小唐，我更喜欢先看步骤再看完整答案。",
            assistant_message="好的，我会记住。",
            agent_state={},
            tool_events=[],
        )
        context = service.read_for_agent(
            actor={"user_id": subject, "role": "student"},
            conversation_id="langmem-live-read",
            course_id="course-probe",
            task_id=None,
            query="我喜欢怎样的回答方式",
            token_budget=1_000,
        )

        assert write.provider == "langmem"
        assert write.provider_status == "ok"
        assert write.written_count >= 2
        assert {fact.profile_axis for fact in context.profile_facts} >= {
            "display_name",
            "response_detail",
        }
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
