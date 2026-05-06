"""Legacy route compatibility — do NOT import from new code.

This module provides backward-compatible access to old route handlers
that have been moved to app/api/. Only legacy adapters should use this.
"""

from __future__ import annotations

# Re-export chat routes for any legacy code that still accesses them directly
from app.api.chat_legacy import router as legacy_chat_router

__all__ = ["legacy_chat_router"]
