from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import runtime_config as module
from app.auth import get_current_user
from app.bootstrap import create_app
from app.services.runtime_config_resolver import RuntimeConfigResolver
from app.services.runtime_config_store import RuntimeConfigStore


def _client(tmp_path, *, role="teacher"):
    store = RuntimeConfigStore(root=tmp_path, master_key="test-key")
    module.runtime_config_store = store
    module.runtime_config_resolver = RuntimeConfigResolver(store)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "teacher-a",
        "role": role,
    }
    return TestClient(app), store


def _draft(client, *, scope="user"):
    return client.post(
        "/api/runtime-config/llm/draft",
        json={
            "scope": scope,
            "values": {
                "base_url": "https://provider.example/v1",
                "api_key": "sk-api-secret-123456",
                "model": "model-a",
            },
        },
    )


def test_runtime_config_api_masks_key_and_requires_verification(tmp_path, monkeypatch):
    client, _store = _client(tmp_path)
    created = _draft(client)
    assert created.status_code == 200
    revision_id = created.json()["revision_id"]
    assert "sk-api-secret" not in created.text

    rejected = client.post(
        "/api/runtime-config/llm/activate",
        json={"scope": "user", "revision_id": revision_id},
    )
    assert rejected.status_code == 409

    monkeypatch.setattr(module, "_verify_provider", lambda *_args: None)
    verified = client.post(
        "/api/runtime-config/llm/verify",
        json={"scope": "user", "revision_id": revision_id},
    )
    assert verified.json()["status"] == "verified"
    activated = client.post(
        "/api/runtime-config/llm/activate",
        json={"scope": "user", "revision_id": revision_id},
    )
    assert activated.json()["status"] == "active"

    listing = client.get("/api/runtime-config")
    assert listing.status_code == 200
    assert "sk-api-secret" not in listing.text
    assert listing.json()["providers"][0]["effective_source"] == "user"


def test_non_admin_cannot_manage_or_read_system_revisions(tmp_path):
    client, _store = _client(tmp_path, role="teacher")
    response = _draft(client, scope="system")
    assert response.status_code == 403
    listing = client.get("/api/runtime-config").json()
    assert listing["can_manage_system"] is False
    assert all(item["system"] is None for item in listing["providers"])


def test_failed_verification_marks_revision_invalid_without_leaking_secret(
    tmp_path, monkeypatch
):
    client, _store = _client(tmp_path)
    revision_id = _draft(client).json()["revision_id"]

    def _fail(*_args):
        raise ValueError("服务连接失败")

    monkeypatch.setattr(module, "_verify_provider", _fail)
    response = client.post(
        "/api/runtime-config/llm/verify",
        json={"scope": "user", "revision_id": revision_id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "invalid"
    assert "sk-api-secret" not in response.text


def test_active_configuration_can_be_disabled_to_restore_fallback(
    tmp_path, monkeypatch
):
    client, _store = _client(tmp_path)
    revision_id = _draft(client).json()["revision_id"]
    monkeypatch.setattr(module, "_verify_provider", lambda *_args: None)
    client.post(
        "/api/runtime-config/llm/verify",
        json={"scope": "user", "revision_id": revision_id},
    )
    client.post(
        "/api/runtime-config/llm/activate",
        json={"scope": "user", "revision_id": revision_id},
    )

    response = client.post(
        "/api/runtime-config/llm/disable",
        json={"scope": "user"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert client.get("/api/runtime-config").json()["providers"][0][
        "effective_source"
    ] == "environment"
