"""Backward-compat re-exports — new code should import from app.api.video directly."""

from __future__ import annotations

from app.api.video import router

__all__ = ["router"]
