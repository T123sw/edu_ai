from __future__ import annotations

from collections.abc import Callable
from typing import Any

from collections.abc import Callable
from typing import Any

from app.chat.runtime.agent_tools.handlers.lesson_plan import handle_generate_lesson_plan
from app.chat.runtime.agent_tools.handlers.outline import handle_draft_outline
from app.chat.runtime.agent_tools.handlers.ppt import handle_generate_ppt
from app.chat.runtime.agent_tools.handlers.quiz import handle_generate_quiz
from app.chat.runtime.agent_tools.handlers.report import handle_generate_report
from app.chat.runtime.agent_tools.handlers.retrieval import handle_rag_search, handle_web_search

ToolHandler = Callable[[str, dict[str, Any], Any], dict[str, Any]]

_GENERATE_HANDLERS: dict[str, ToolHandler] = {
    "generate_report":      handle_generate_report,
    "generate_ppt":         handle_generate_ppt,
    "generate_lesson_plan": handle_generate_lesson_plan,
    "generate_quiz":        handle_generate_quiz,
}


def get_tool_handler(name: str) -> ToolHandler | None:
    if name == "rag_search":
        return handle_rag_search
    if name == "web_search":
        return handle_web_search
    if name == "draft_outline":
        return handle_draft_outline
    return _GENERATE_HANDLERS.get(name)
