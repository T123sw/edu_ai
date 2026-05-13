"""Legacy compatibility layer."""

from __future__ import annotations

__all__ = ["CompatChatService", "LegacyChatRuntime"]


def __getattr__(name: str):
    if name == "CompatChatService":
        from .compat_service import CompatChatService

        return CompatChatService
    if name == "LegacyChatRuntime":
        from .legacy_chat_runtime import LegacyChatRuntime

        return LegacyChatRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
