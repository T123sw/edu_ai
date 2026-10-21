from __future__ import annotations

import pytest

from app.services.personal_tool_access import (
    PersonalToolAccessDenied,
    list_personal_tools_for_role,
    require_personal_tool,
)


def _tool_ids(role: str) -> list[str]:
    return [item.tool_id for item in list_personal_tools_for_role(role)]


@pytest.mark.parametrize("role", ["teacher", "student", "admin", "user", "unknown", ""])
def test_authenticated_accounts_receive_the_same_tools(role):
    expected = ["report", "mind_map", "quiz", "classroom", "flashcard", "game", "podcast", "scenario"]
    assert _tool_ids(role) == expected
    for tool_id in expected:
        assert require_personal_tool(role, tool_id).tool_id == tool_id


@pytest.mark.parametrize("role", ["teacher", "student", "admin", "user", ""])
def test_unknown_tools_are_rejected(role):
    with pytest.raises(PersonalToolAccessDenied) as exc_info:
        require_personal_tool(role, "unknown")
    assert exc_info.value.system_role == role
    assert exc_info.value.tool_id == "unknown"


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

