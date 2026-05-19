from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.chat.runtime.agent_tools.constants import TOOL_TO_WORKFLOW
from app.chat.runtime.agent_tools.handlers.generation_stub import handle_generate_stub
from app.chat.runtime.agent_tools.handlers.outline import handle_draft_outline
from app.chat.runtime.agent_tools.handlers.retrieval import handle_rag_search, handle_web_search

ToolHandler = Callable[[str, dict[str, Any], Any], dict[str, Any]]


def get_tool_handler(name: str) -> ToolHandler | None:
    if name == "rag_search":
        return handle_rag_search
    if name == "web_search":
        return handle_web_search
    if name == "draft_outline":
        return handle_draft_outline
    if name in TOOL_TO_WORKFLOW:
        return handle_generate_stub
    return None
