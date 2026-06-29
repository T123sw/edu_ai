"""Phase 6-A.2 — serve locally-cached search images.

GET /api/images/searched/{filename}
    filename = "{16-char-hex-hash}.{ext}"
    auth   = HTTPBearer (any logged-in user; full ACL pending course-enrollment data)
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import auth_manager
from core import Config


router = APIRouter(prefix="/api/images/searched", tags=["images"])

security = HTTPBearer()

# Strict filename pattern — 16 hex chars + allowed image extension
_FILENAME_RE = re.compile(r"^[0-9a-f]{16}\.(jpg|jpeg|png|webp|gif)$")


def _require_login(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Phase 6-A.2 auth — Plan §三 走向 B: must be logged in, no role/course ACL yet."""
    try:
        return auth_manager.get_current_user(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc) or "unauthorized") from exc


@router.get("/{filename}")
def get_searched_image(
    filename: str,
    _user: dict = Depends(_require_login),
):
    path = _resolve_safe_path(filename)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="image not found")

    return FileResponse(
        path,
        media_type=_guess_mime(path),
        headers={
            # Treat cached images as immutable for a day; agent runs may re-emit
            # the same hash so we still want the browser to revalidate occasionally.
            "Cache-Control": "private, max-age=86400",
        },
    )


def _resolve_safe_path(filename: str) -> Path | None:
    """Strictly validate filename and locate the file under any date partition.

    Defends against path traversal (`..`, `/`, `\\`) by enforcing the hash-format
    regex BEFORE any filesystem access.
    """
    if not _FILENAME_RE.match(filename):
        return None
    storage_root = Path(Config.SEARCHED_IMAGE_STORAGE_ROOT)
    if not storage_root.exists():
        return None
    for date_dir in storage_root.iterdir():
        if not date_dir.is_dir():
            continue
        candidate = date_dir / filename
        if candidate.is_file():
            # Final safety: ensure resolved path is inside the storage root
            try:
                candidate.resolve().relative_to(storage_root.resolve())
            except ValueError:
                continue
            return candidate
    return None


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"
