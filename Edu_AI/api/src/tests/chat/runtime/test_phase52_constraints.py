"""Phase 5.2 C: planner attaches step constraints so LLM/Vision reflectors activate."""
from app.chat.runtime.nodes.planner import _attach_step_constraints


def test_retrieve_context_gets_relevance_and_source_checks():
    plan = {
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "搜索", "internal_action": "retrieve_context",
             "expected_tools": ["rag_search"], "constraints": {}},
        ],
    }
    _attach_step_constraints(plan)
    c = plan["steps"][0]["constraints"]
    assert c.get("check_relevance") is True
    assert c.get("require_sources") is True
    assert c.get("min_sources", 0) >= 1
    # Reports don't need images
    assert "require_images" not in c


def test_retrieve_context_for_ppt_also_requires_images():
    plan = {
        "resource_type": "ppt",
        "steps": [
            {"index": 1, "user_title": "搜索", "internal_action": "retrieve_context",
             "expected_tools": ["web_search"], "constraints": {}},
        ],
    }
    _attach_step_constraints(plan)
    c = plan["steps"][0]["constraints"]
    assert c.get("require_images") is True


def test_draft_outline_gets_coherence_check():
    plan = {
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "大纲", "internal_action": "draft_outline",
             "expected_tools": ["draft_outline"], "constraints": {}},
        ],
    }
    _attach_step_constraints(plan)
    c = plan["steps"][0]["constraints"]
    assert c.get("check_coherence") is True
    assert c.get("min_chapters", 0) >= 3


def test_existing_constraints_are_preserved():
    plan = {
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "搜索", "internal_action": "retrieve_context",
             "expected_tools": ["rag_search"],
             "constraints": {"check_relevance": False, "min_sources": 5}},
        ],
    }
    _attach_step_constraints(plan)
    c = plan["steps"][0]["constraints"]
    # User-specified values must NOT be overwritten by defaults
    assert c["check_relevance"] is False
    assert c["min_sources"] == 5
    # But unset keys still get defaults
    assert c.get("require_sources") is True


def test_generate_resource_step_unchanged():
    plan = {
        "resource_type": "report",
        "steps": [
            {"index": 1, "user_title": "生成", "internal_action": "generate_resource",
             "expected_tools": ["generate_report"], "constraints": {}},
        ],
    }
    _attach_step_constraints(plan)
    # No defaults for generate_resource
    assert plan["steps"][0]["constraints"] == {}


def test_fallback_plan_includes_confirm_outline_step():
    """C4: fallback should include a confirm_outline step before generate_resource."""
    from app.chat.runtime.nodes.planner import _fallback_plan

    plan = _fallback_plan("帮我写一份机器学习报告", state={}, capability=None)
    actions = [s["internal_action"] for s in plan["steps"]]
    assert "draft_outline" in actions
    assert "confirm_outline" in actions
    assert "generate_resource" in actions
    # confirm must come before generate
    assert actions.index("confirm_outline") < actions.index("generate_resource")
