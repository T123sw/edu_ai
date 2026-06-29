"""Phase 6-A.2 — FastAPI route tests for /api/images/searched/{filename}.

Coverage:
  - valid filename + existing file → 200 + correct mime
  - valid filename + missing file → 404
  - path traversal attempts → 404 (regex rejects before filesystem touch)
  - missing / invalid auth token → 401
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.searched_images import router


@pytest.fixture
def populated_storage(tmp_path):
    """Set up storage root with one valid image under today's date partition."""
    today_dir = tmp_path / "20260629"
    today_dir.mkdir(parents=True)
    valid_path = today_dir / "abcdef1234567890.png"
    valid_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return tmp_path, valid_path


@pytest.fixture
def client_with_storage(populated_storage):
    storage_root, _ = populated_storage
    app = FastAPI()
    app.include_router(router)
    with patch("app.api.searched_images.Config.SEARCHED_IMAGE_STORAGE_ROOT", storage_root):
        yield TestClient(app), populated_storage


@pytest.fixture
def auth_headers():
    """Bypass auth by patching auth_manager.get_current_user to always succeed."""
    with patch("app.api.searched_images.auth_manager") as mock_auth:
        mock_auth.get_current_user.return_value = {"username": "alice", "role": "teacher"}
        yield {"Authorization": "Bearer test-token"}


def test_route_serves_existing_image_with_correct_mime(client_with_storage, auth_headers):
    client, (_, valid_path) = client_with_storage
    response = client.get(f"/api/images/searched/{valid_path.name}", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == valid_path.read_bytes()


def test_route_returns_404_for_nonexistent_file(client_with_storage, auth_headers):
    client, _ = client_with_storage
    response = client.get("/api/images/searched/0000000000000000.png", headers=auth_headers)
    assert response.status_code == 404


def test_route_returns_404_for_path_traversal_attempt(client_with_storage, auth_headers):
    client, _ = client_with_storage
    # Try various traversal payloads — all must be rejected before any FS access
    for payload in [
        "../etc/passwd",
        "..%2Fetc%2Fpasswd",
        "abcd1234.png/../../secret",
        "subdir/abcdef1234567890.png",
        "abcdef1234567890.png.exe",
        "ABCDEF1234567890.png",         # uppercase rejected by regex
        "abcdef1234567890.bmp",         # bmp not in allowed exts
        "abcdef123456789.png",          # 15 chars (not 16)
        "abcdef12345678901.png",        # 17 chars
    ]:
        response = client.get(f"/api/images/searched/{payload}", headers=auth_headers)
        assert response.status_code in (404, 422), \
            f"{payload!r} returned {response.status_code} (expected 404/422)"


def test_route_returns_401_without_auth_token():
    """No Authorization header → 401/403 (FastAPI's HTTPBearer auto-rejects)."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/images/searched/abcdef1234567890.png")
    # HTTPBearer raises 403 by default when no creds are supplied
    assert response.status_code in (401, 403)


def test_route_returns_401_when_auth_manager_rejects_token():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    with patch("app.api.searched_images.auth_manager") as mock_auth:
        mock_auth.get_current_user.side_effect = Exception("invalid token")
        response = client.get(
            "/api/images/searched/abcdef1234567890.png",
            headers={"Authorization": "Bearer bad-token"},
        )
    assert response.status_code == 401
