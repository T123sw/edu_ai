from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_database_health_route_is_non_blocking_when_database_is_not_configured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from app.api.health import router

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/health/database")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "status": "disabled",
        "message": "database is not configured",
    }
