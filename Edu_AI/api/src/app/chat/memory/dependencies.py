from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine

from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.domain import AgentMemoryContext, MemoryWriteResult
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.service import AgentMemoryService
from app.chat.memory.settings import AgentMemorySettings


class UnavailableAgentMemoryService:
    available = False
    unavailable_reason = "DATABASE_URL is not configured"

    def read_for_agent(self, **kwargs) -> AgentMemoryContext:
        return AgentMemoryContext(retrieval_notes=["agent_memory_database_unavailable"])

    def read(self, **kwargs) -> dict:
        return {"summary": "", "context": {}}

    def persist_turn(self, **kwargs) -> MemoryWriteResult:
        return MemoryWriteResult(provider_status="disabled")


@lru_cache(maxsize=4)
def _build_agent_memory_service(database_url: str) -> AgentMemoryService:
    settings = AgentMemorySettings.from_environment()
    engine = create_engine(database_url, pool_pre_ping=True)
    repository = SqlAlchemyMemoryRepository(engine)
    return AgentMemoryService(
        repository=repository,
        settings=settings,
        langmem_adapter=LangMemAdapter(settings=settings),
    )


def get_agent_memory_service() -> AgentMemoryService:
    database_url = str(os.getenv("DATABASE_URL", "")).strip()
    if not database_url:
        return UnavailableAgentMemoryService()
    service = _build_agent_memory_service(database_url)
    service.available = True
    return service
