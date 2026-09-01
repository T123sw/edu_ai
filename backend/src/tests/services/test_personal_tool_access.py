from __future__ import annotations

import pytest

from app.services.personal_tool_access import (
    PersonalToolAccessDenied,
    list_personal_tools_for_role,
    require_personal_tool,
)


def _tool_ids(role: str) -> list[str]:
    return [item.tool_id for item in list_personal_tools_for_role(role)]


def test_teacher_and_student_receive_exact_role_scoped_tool_catalogs():
    assert _tool_ids("teacher") == [
        "report",
        "mind_map",
        "quiz",
        "classroom",
        "lesson_plan",
        "blog",
    ]
    assert _tool_ids("student") == [
        "report",
        "mind_map",
        "quiz",
        "classroom",
        "flashcard",
        "game",
    ]
    assert _tool_ids("admin") == _tool_ids("teacher")


@pytest.mark.parametrize(
    ("role", "tool_id"),
    [
        ("student", "lesson_plan"),
        ("student", "blog"),
        ("teacher", "flashcard"),
        ("teacher", "game"),
        ("admin", "flashcard"),
        ("unknown", "report"),
        ("student", "unknown"),
    ],
)
def test_require_personal_tool_rejects_disallowed_roles_and_tools(
    role: str,
    tool_id: str,
):
    with pytest.raises(PersonalToolAccessDenied) as exc_info:
        require_personal_tool(role, tool_id)

    assert exc_info.value.system_role == role
    assert exc_info.value.tool_id == tool_id


def test_every_catalog_entry_is_personal_only_and_non_publishable():
    for role in ("teacher", "student", "admin"):
        for definition in list_personal_tools_for_role(role):
            assert definition.output_scope == "personal"
            assert definition.publish_capability is None
            assert definition.required_course_capabilities == ("read",)
            assert definition.allowed_source_scopes == (
                "none",
                "personal",
                "course",
            )


def test_catalog_is_immutable_and_stable_between_calls():
    first = list_personal_tools_for_role("student")
    second = list_personal_tools_for_role("student")

    assert isinstance(first, tuple)
    assert first == second
    assert first is not second

