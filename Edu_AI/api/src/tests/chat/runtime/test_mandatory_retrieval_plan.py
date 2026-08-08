from types import SimpleNamespace

from app.chat.runtime.nodes.planner import _ensure_mandatory_retrieval_when_enabled


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
        "draft_outline",
        "retrieve_context",
        "confirm_outline",
    ]
    assert plan["steps"][1]["expected_tools"] == ["rag_search", "web_search"]
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
