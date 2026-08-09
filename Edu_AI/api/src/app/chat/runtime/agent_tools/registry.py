from __future__ import annotations

from collections.abc import Callable
from typing import Any

from collections.abc import Callable
from typing import Any

from app.chat.runtime.agent_tools.handlers.image_search import handle_image_search
from app.chat.runtime.agent_tools.handlers.lesson_plan import handle_generate_lesson_plan
from app.chat.runtime.agent_tools.handlers.outline import handle_draft_outline
from app.chat.runtime.agent_tools.handlers.ppt import handle_generate_ppt
from app.chat.runtime.agent_tools.handlers.quiz import handle_generate_quiz
from app.chat.runtime.agent_tools.handlers.report import handle_generate_report
from app.chat.runtime.agent_tools.handlers.retrieval import handle_rag_search, handle_web_search
from app.chat.runtime.agent_tools.handlers.resource import handle_generate_resource
from app.chat.runtime.agent_tools.handlers.classroom import handle_generate_classroom
from app.chat.runtime.agent_tools.handlers.verification import handle_verify_task
from app.chat.runtime.agent_tools.handlers.control import handle_cancel_task, handle_query_task_status

ToolHandler = Callable[[str, dict[str, Any], Any], dict[str, Any]]

_GENERATE_HANDLERS: dict[str, ToolHandler] = {
    "generate_report":      handle_generate_report,
    "generate_ppt":         handle_generate_ppt,
    "generate_lesson_plan": handle_generate_lesson_plan,
    "generate_quiz":        handle_generate_quiz,
    "generate_blog":        handle_generate_resource,
    "generate_flashcard":   handle_generate_resource,
    "generate_graph":       handle_generate_resource,
    "generate_game":        handle_generate_resource,
    "generate_classroom":   handle_generate_classroom,
}


def get_tool_handler(name: str) -> ToolHandler | None:
    if name == "rag_search":
        return handle_rag_search
    if name == "web_search":
        return handle_web_search
    if name == "image_search":
        return handle_image_search
    if name == "draft_outline":
        return handle_draft_outline
    if name == "verify_task":
        return handle_verify_task
    if name == "query_task_status":
        return handle_query_task_status
    if name == "cancel_task":
        return handle_cancel_task
    return _GENERATE_HANDLERS.get(name)
