from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.chat.memory import api as memory_api
from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.repository import SqlAlchemyMemoryRepository
from app.chat.memory.service import AgentMemoryService
from app.chat.memory.settings import AgentMemorySettings
from app.database import Base


def test_profile_api_enforces_owner_and_invalidation(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
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
    monkeypatch.setattr(memory_api, "get_agent_memory_service", lambda: service)

    active_user = {"username": "student-a", "role": "student"}
    app = FastAPI()
    app.include_router(memory_api.router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    client = TestClient(app)

    update = client.put(
        "/api/agent-memory/profile/response_detail",
        json={"value": "用户偏好简短回答"},
    )
    assert update.status_code == 200
    memory_id = update.json()["memory"]["memory_id"]

    profile = client.get("/api/agent-memory/profile")
    assert profile.status_code == 200
    assert [item["value"] for item in profile.json()["profile_facts"]] == [
        "用户偏好简短回答"
    ]

    active_user["username"] = "student-b"
    assert client.get("/api/agent-memory/profile").json()["profile_facts"] == []
    assert client.delete(f"/api/agent-memory/items/{memory_id}").status_code == 404

    active_user["username"] = "student-a"
    assert client.delete(f"/api/agent-memory/items/{memory_id}").status_code == 200
    assert client.get("/api/agent-memory/profile").json()["profile_facts"] == []
