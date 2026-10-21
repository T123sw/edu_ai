"""Shared tool catalog for authenticated users; resource ownership is checked separately."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast


PersonalToolId = Literal[
    "podcast",
    "scenario",
    "report",
    "mind_map",
    "quiz",
    "classroom",
    "lesson_plan",
    "blog",
    "flashcard",
    "game",
]
PersonalSourceScope = Literal["none", "personal", "course"]
PersonalOutputScope = Literal["personal"]


@dataclass(frozen=True)
class PersonalToolDefinition:
    tool_id: PersonalToolId
    required_course_capabilities: tuple[Literal["read"], ...] = ("read",)
    allowed_source_scopes: tuple[PersonalSourceScope, ...] = (
        "none",
        "personal",
        "course",
    )
    output_scope: PersonalOutputScope = "personal"
    publish_capability: None = None


class PersonalToolAccessDenied(PermissionError):
    def __init__(self, *, system_role: str, tool_id: str) -> None:
        normalized_role = str(system_role or "").strip()
        normalized_tool_id = str(tool_id or "").strip()
        super().__init__(
            f"system role {normalized_role or '<unknown>'} cannot use "
            f"personal tool {normalized_tool_id or '<unknown>'}"
        )
        self.system_role = normalized_role
        self.tool_id = normalized_tool_id


_TOOL_DEFINITIONS: tuple[PersonalToolDefinition, ...] = tuple(
    PersonalToolDefinition(tool_id)
    for tool_id in (
        "report", "mind_map", "quiz", "classroom",
        "flashcard", "game", "podcast", "scenario",
    )
)


def list_personal_tools_for_role(
    system_role: str,
) -> tuple[PersonalToolDefinition, ...]:
    """Keep the legacy call signature; account roles no longer filter tools."""
    return _TOOL_DEFINITIONS


def require_personal_tool(
    system_role: str,
    tool_id: str,
) -> PersonalToolDefinition:
    role = str(system_role or "").strip()
    normalized_tool_id = str(tool_id or "").strip()
    for definition in _TOOL_DEFINITIONS:
        if definition.tool_id == normalized_tool_id:
            return definition
    raise PersonalToolAccessDenied(
        system_role=role,
        tool_id=normalized_tool_id,
    )


def as_personal_tool_id(tool_id: str) -> PersonalToolId:
    """Validate a boundary value while preserving a narrow type for callers."""

    definition = next(
        (
            item
            for item in _TOOL_DEFINITIONS
            if item.tool_id == str(tool_id or "").strip()
        ),
        None,
    )
    if definition is None:
        raise PersonalToolAccessDenied(system_role="", tool_id=tool_id)
    return cast(PersonalToolId, definition.tool_id)

