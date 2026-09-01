from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth as module
from core.user_storage import UserStorage


def _client(tmp_path):
    storage = UserStorage(str(tmp_path / "users.json"))
    storage.create_user("teacher-a", "old-password", "teacher")
    module.user_storage = storage
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: {
        "username": "teacher-a",
        "role": "teacher",
    }
    return TestClient(app), storage


def test_profile_reads_and_updates_real_user_storage(tmp_path):
    client, storage = _client(tmp_path)
    initial = client.get("/api/auth/me")
    assert initial.status_code == 200
    assert initial.json()["username"] == "teacher-a"
    assert "林知夏" not in initial.text

    updated = client.put(
        "/api/auth/me",
        json={
            "display_name": "王老师",
            "email": "teacher@example.com",
            "phone": "13800000000",
            "department": "课程研发中心",
            "bio": "负责计算思维课程。",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "王老师"
    assert storage.get_user("teacher-a")["email"] == "teacher@example.com"
    assert "password_hash" not in updated.text


def test_password_change_rejects_wrong_current_password_and_updates_hash(tmp_path):
    client, storage = _client(tmp_path)
    rejected = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "new-password-123"},
    )
    assert rejected.status_code == 400
    assert storage.verify_password("teacher-a", "old-password") is True

    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": "old-password", "new_password": "new-password-123"},
    )
    assert changed.status_code == 200
    assert storage.verify_password("teacher-a", "old-password") is False
    assert storage.verify_password("teacher-a", "new-password-123") is True
    assert storage.get_user("teacher-a")["password_hash"].startswith("pbkdf2_sha256$")


def test_avatar_upload_is_owner_scoped_and_validated(tmp_path, monkeypatch):
    client, storage = _client(tmp_path)
    monkeypatch.setattr(module.Config, "STORAGE_ROOT", tmp_path / "storage")
    rejected = client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.txt", b"not-an-image", "text/plain")},
    )
    assert rejected.status_code == 400

    uploaded = client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.png", b"small-png-fixture", "image/png")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["avatar_url"] == "/api/auth/avatar"
    assert storage.get_user("teacher-a")["avatar_path"]
    served = client.get("/api/auth/avatar")
    assert served.status_code == 200
    assert served.content == b"small-png-fixture"


def test_public_registration_cannot_create_an_admin(tmp_path):
    storage = UserStorage(str(tmp_path / "users.json"))
    module.user_storage = storage
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={"username": "new-admin", "password": "safe-password", "role": "admin"},
    )
    assert response.status_code == 400
    assert storage.get_user("new-admin") is None
