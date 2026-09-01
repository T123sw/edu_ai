from app.workspace_scope import (
    SCOPE_TYPE_COURSE,
    SCOPE_TYPE_KNOWLEDGE_POINT,
    collect_scope_ids_for_query,
    normalize_workspace_scope,
)


def test_normalize_workspace_scope_defaults_course_root():
    normalized = normalize_workspace_scope(course_id="computational-thinking")
    assert normalized == {
        "course_id": "computational-thinking",
        "scope_type": SCOPE_TYPE_COURSE,
        "scope_id": None,
    }


def test_normalize_workspace_scope_requires_scope_id_for_knowledge_point():
    try:
        normalize_workspace_scope(
            course_id="computational-thinking",
            scope_type=SCOPE_TYPE_KNOWLEDGE_POINT,
            scope_id="",
        )
    except ValueError as exc:
        assert "scope_id" in str(exc)
    else:
        raise AssertionError("normalize_workspace_scope should reject empty scope_id")


def test_collect_scope_ids_for_query_returns_parent_and_descendants():
    root = {
        "id": "root",
        "children": [
            {
                "id": "sorting",
                "children": [
                    {"id": "bubble", "children": []},
                    {"id": "quick", "children": []},
                ],
            },
            {"id": "graphs", "children": []},
        ],
    }

    scope_ids = collect_scope_ids_for_query(
        root,
        scope_type=SCOPE_TYPE_KNOWLEDGE_POINT,
        scope_id="sorting",
    )
    assert scope_ids == {"sorting", "bubble", "quick"}
