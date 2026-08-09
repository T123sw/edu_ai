"""Role-scoped authorization for resources saved to a user's private space."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast


PersonalToolId = Literal[
    "report",
    "ppt",
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
    allowed_system_roles: frozenset[str]
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


_TEACHER_ROLES = frozenset({"teacher", "admin"})
_STUDENT_ROLES = frozenset({"student"})
_SHARED_ROLES = _TEACHER_ROLES | _STUDENT_ROLES

_TOOL_DEFINITIONS: tuple[PersonalToolDefinition, ...] = (
    PersonalToolDefinition("report", _SHARED_ROLES),
    PersonalToolDefinition("ppt", _SHARED_ROLES),
    PersonalToolDefinition("mind_map", _SHARED_ROLES),
    PersonalToolDefinition("quiz", _SHARED_ROLES),
    PersonalToolDefinition("classroom", _SHARED_ROLES),
    PersonalToolDefinition("lesson_plan", _TEACHER_ROLES),
    PersonalToolDefinition("blog", _TEACHER_ROLES),
    PersonalToolDefinition("flashcard", _STUDENT_ROLES),
    PersonalToolDefinition("game", _STUDENT_ROLES),
)


def list_personal_tools_for_role(
    system_role: str,
) -> tuple[PersonalToolDefinition, ...]:
    role = str(system_role or "").strip()
    return tuple(
        definition
        for definition in _TOOL_DEFINITIONS
        if role in definition.allowed_system_roles
    )


def require_personal_tool(
    system_role: str,
    tool_id: str,
) -> PersonalToolDefinition:
    role = str(system_role or "").strip()
    normalized_tool_id = str(tool_id or "").strip()
    for definition in _TOOL_DEFINITIONS:
        if definition.tool_id == normalized_tool_id:
            if role in definition.allowed_system_roles:
                return definition
            break
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

