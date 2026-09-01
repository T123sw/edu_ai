from types import SimpleNamespace

from app.chat.runtime.nodes.planner import (
    _enforce_explicit_resource_type,
    _ensure_mandatory_retrieval_when_enabled,
    _ensure_outline_confirmation_boundary,
)


def test_mandatory_retrieval_is_inserted_when_planner_omits_it():
    plan = {
        "subject": "冒泡排序",
        "resource_type": "report",
        "steps": [
            {
                "index": 1,
                "internal_action": "draft_outline",
                "expected_tools": ["draft_outline"],
            },
            {
                "index": 2,
                "internal_action": "confirm_outline",
                "expected_tools": [],
            },
        ],
    }
    capability = SimpleNamespace(allow_rag=True, allow_web=True)

    _ensure_mandatory_retrieval_when_enabled(plan, capability)

    assert [step["internal_action"] for step in plan["steps"]] == [
        "retrieve_context",
        "draft_outline",
        "confirm_outline",
    ]
    assert plan["steps"][0]["expected_tools"] == ["rag_search", "web_search"]
    assert [step["index"] for step in plan["steps"]] == [1, 2, 3]


def test_mandatory_retrieval_adds_missing_enabled_tool_to_existing_step():
    plan = {
        "subject": "冒泡排序",
        "resource_type": "report",
        "steps": [
            {
                "index": 1,
                "internal_action": "retrieve_context",
                "expected_tools": ["rag_search"],
            },
        ],
    }
    capability = SimpleNamespace(allow_rag=True, allow_web=True)

    _ensure_mandatory_retrieval_when_enabled(plan, capability)

    assert plan["steps"][0]["expected_tools"] == ["rag_search", "web_search"]


def test_mandatory_retrieval_moves_existing_step_before_direct_answer():
    plan = {
        "subject": "链表如何实现",
        "resource_type": "unknown",
        "steps": [
            {
                "index": 1,
                "user_title": "生成链表实现的详细解答",
                "internal_action": "answer_question",
                "expected_tools": [],
            },
            {
                "index": 2,
                "user_title": "检索已启用的资料来源",
                "internal_action": "retrieve_context",
                "expected_tools": ["rag_search"],
            },
        ],
    }
    capability = SimpleNamespace(allow_rag=True, allow_web=False)

    _ensure_mandatory_retrieval_when_enabled(plan, capability)

    assert [step["internal_action"] for step in plan["steps"]] == [
        "retrieve_context",
        "answer_question",
    ]
    assert [step["index"] for step in plan["steps"]] == [1, 2]


def test_mandatory_retrieval_is_first_even_for_nonstandard_planner_action():
    plan = {
        "subject": "链表如何实现",
        "resource_type": "unknown",
        "steps": [
            {
                "index": 1,
                "user_title": "解释链表实现",
                "internal_action": "other",
                "expected_tools": [],
            }
        ],
    }

    _ensure_mandatory_retrieval_when_enabled(
        plan,
        SimpleNamespace(allow_rag=True, allow_web=False),
    )

    assert [step["internal_action"] for step in plan["steps"]] == [
        "retrieve_context",
        "other",
    ]
    assert plan["steps"][0]["expected_tools"] == ["rag_search"]


def test_mandatory_retrieval_merges_duplicate_retrieval_steps():
    plan = {
        "steps": [
            {"index": 1, "internal_action": "retrieve_context", "expected_tools": ["rag_search"]},
            {"index": 2, "internal_action": "answer_question", "expected_tools": []},
            {"index": 3, "internal_action": "retrieve_context", "expected_tools": ["web_search"]},
        ]
    }
    capability = SimpleNamespace(allow_rag=True, allow_web=True)

    _ensure_mandatory_retrieval_when_enabled(plan, capability)

    assert [step["internal_action"] for step in plan["steps"]] == [
        "retrieve_context",
        "answer_question",
    ]
    assert plan["steps"][0]["expected_tools"] == ["rag_search", "web_search"]


def test_initial_report_plan_cannot_skip_confirmation_or_submit_generation():
    plan = {
        "subject": "快速排序",
        "resource_type": "report",
        "steps": [
            {"index": 1, "internal_action": "draft_outline", "expected_tools": ["draft_outline"]},
            {"index": 2, "internal_action": "retrieve_context", "expected_tools": ["web_search"]},
            {"index": 3, "internal_action": "generate_resource", "expected_tools": ["generate_report"]},
        ],
    }

    _ensure_outline_confirmation_boundary(plan, {})

    assert [step["internal_action"] for step in plan["steps"]] == [
        "draft_outline",
        "retrieve_context",
        "confirm_outline",
    ]
    assert all(
        not any(tool.startswith("generate_") for tool in step["expected_tools"])
        for step in plan["steps"]
    )


def test_confirm_turn_keeps_generation_step_when_outline_existed_at_turn_start():
    plan = {
        "resource_type": "report",
        "steps": [
            {"index": 1, "internal_action": "generate_resource", "expected_tools": ["generate_report"]}
        ],
    }

    _ensure_outline_confirmation_boundary(
        plan,
        {"active_draft_outline": {"subject": "快速排序"}},
    )

    assert plan["steps"][0]["expected_tools"] == ["generate_report"]


def test_explicit_blog_request_overrides_report_like_llm_plan():
    plan = {
        "subject": "快速排序",
        "resource_type": "report",
        "steps": [
            {"index": 1, "internal_action": "draft_outline", "expected_tools": ["draft_outline"]}
        ],
    }

    _enforce_explicit_resource_type(plan, "帮我生成一篇快速排序的教学博客")

    assert plan["resource_type"] == "blog"
    assert plan["steps"] == [
        {
            "index": 1,
            "user_title": "生成快速排序教学博客",
            "internal_action": "generate_resource",
            "expected_tools": ["generate_blog"],
        }
    ]
