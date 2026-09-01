"""Backward-compat re-exports — new code should import from app.api.deepsearch directly."""

from __future__ import annotations

from app.api.deepsearch import router

__all__ = ["router"]
