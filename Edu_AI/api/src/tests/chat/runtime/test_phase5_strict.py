"""Phase 5 tests: strict mode, ToolMeta, parallel execution."""
from unittest.mock import patch

from app.chat.runtime.agent_tools.schemas import (
    SCHEMA_DRAFT_OUTLINE,
    SCHEMA_GENERATE_REPORT,
    SCHEMA_RAG_SEARCH,
    SCHEMA_WEB_SEARCH,
    filter_schemas_by_step,
)
from app.chat.runtime.agent_tools.tool_meta import (
    get_tool_meta,
    is_parallel_safe,
)


# ─── ToolMeta unit tests ──────────────────────────────────────────────────────

def test_tool_meta_rag_search_is_parallel_safe():
    meta = get_tool_meta("rag_search")
    assert meta.parallel_safe is True
    assert meta.mutates_state is False


def test_tool_meta_generate_report_mutates_state():
    meta = get_tool_meta("generate_report")
    assert meta.parallel_safe is False
    assert meta.mutates_state is True
    assert "draft_outline" in meta.depends_on


def test_tool_meta_unknown_tool_returns_default():
    meta = get_tool_meta("nonexistent_tool")
    assert meta.parallel_safe is False
    assert meta.mutates_state is False


def test_is_parallel_safe_single_tool():
    assert is_parallel_safe(["rag_search"]) is True


def test_is_parallel_safe_two_read_only_tools():
    assert is_parallel_safe(["rag_search", "web_search"]) is True


def test_is_parallel_safe_mixed_tools():
    assert is_parallel_safe(["rag_search", "generate_report"]) is False


def test_is_parallel_safe_two_mutating_tools():
    assert is_parallel_safe(["generate_report", "generate_quiz"]) is False


def test_is_parallel_safe_respects_dependencies():
    assert is_parallel_safe(["draft_outline", "generate_report"]) is False


# ─── filter_schemas_by_step ───────────────────────────────────────────────────

def test_filter_schemas_keeps_only_expected_tools():
    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_WEB_SEARCH, SCHEMA_DRAFT_OUTLINE, SCHEMA_GENERATE_REPORT]
    filtered = filter_schemas_by_step(all_schemas, ["rag_search", "web_search"])
    names = [s["function"]["name"] for s in filtered]
    assert names == ["rag_search", "web_search"]


def test_filter_schemas_empty_expected_returns_all():
    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_WEB_SEARCH]
    filtered = filter_schemas_by_step(all_schemas, [])
    assert filtered == all_schemas


# ─── Executor strict-mode schema filtering ────────────────────────────────────

def test_executor_filter_tool_schemas_strict_mode():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_DRAFT_OUTLINE, SCHEMA_GENERATE_REPORT]
    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [
                {"index": 0, "user_title": "起草大纲", "expected_tools": ["draft_outline"]},
            ],
        },
    }
    filtered = _filter_tool_schemas_for_step(all_schemas, state)
    names = [s["function"]["name"] for s in filtered]
    assert names == ["draft_outline"]


def test_executor_no_filter_in_guided_mode():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_DRAFT_OUTLINE]
    state = {
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [{"index": 0, "expected_tools": ["draft_outline"]}],
        },
    }
    filtered = _filter_tool_schemas_for_step(all_schemas, state)
    assert filtered == all_schemas


def test_executor_no_filter_in_display_only_mode():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_DRAFT_OUTLINE]
    state = {"plan_mode": "display_only", "plan_step_index": 0,
             "current_plan": {"steps": [{"index": 0, "expected_tools": ["draft_outline"]}]}}
    filtered = _filter_tool_schemas_for_step(all_schemas, state)
    assert filtered == all_schemas


# ─── tools_node strict enforcement ────────────────────────────────────────────

def test_enforce_strict_mode_marks_out_of_bounds_calls():
    from app.chat.runtime.nodes.tools import _enforce_strict_mode

    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {"steps": [{"index": 0, "expected_tools": ["draft_outline"]}]},
    }
    calls = [
        {"id": "1", "name": "draft_outline", "args": {}},
        {"id": "2", "name": "generate_report", "args": {}},
    ]
    out = _enforce_strict_mode(calls, state)
    assert out[0].get("_rejected_reason") is None
    assert "strict模式" in out[1]["_rejected_reason"]


def test_enforce_strict_mode_passes_through_in_guided_mode():
    from app.chat.runtime.nodes.tools import _enforce_strict_mode

    state = {
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {"steps": [{"index": 0, "expected_tools": ["draft_outline"]}]},
    }
    calls = [{"id": "1", "name": "generate_report", "args": {}}]
    out = _enforce_strict_mode(calls, state)
    assert out[0].get("_rejected_reason") is None


# ─── Parallel execution ────────────────────────────────────────────────────────

def test_execute_in_parallel_runs_concurrently():
    """Smoke test — parallel execution returns same result count and faster than sequential."""
    import time
    from types import SimpleNamespace
    from app.chat.runtime.agent_tools import ToolExecutionContext
    from app.chat.runtime.nodes.tools import _execute_in_parallel

    calls = [
        {"id": "1", "name": "rag_search", "args": {"query": "test1"}},
        {"id": "2", "name": "web_search", "args": {"query": "test2"}},
    ]

    def slow_rag(**kw):
        time.sleep(0.1)
        return {"payload": {"answer": "rag_result", "sources": []}}

    def slow_web(**kw):
        time.sleep(0.1)
        return {"payload": {"summary": "web_result", "sources": []}}

    capability = SimpleNamespace(allow_rag=True, allow_web=True, selected_doc_ids=[])
    request = SimpleNamespace(owner="test", conversation_id="c1")
    ctx = ToolExecutionContext(
        capability=capability, max_steps=10,
        rag_retriever=slow_rag, web_retriever=slow_web, request=request,
    )

    t0 = time.perf_counter()
    results = _execute_in_parallel(calls, ctx)
    elapsed = time.perf_counter() - t0

    assert len(results) == 2
    # parallel should be ~0.1s, sequential would be ~0.2s
    assert elapsed < 0.18, f"expected parallel < 0.18s but got {elapsed}"


def test_execute_in_parallel_handles_rejected_calls():
    from app.chat.runtime.nodes.tools import _execute_in_parallel

    calls = [
        {"id": "1", "name": "draft_outline", "args": {}, "_rejected_reason": "test reject"},
    ]

    class _Ctx:
        pass

    results = _execute_in_parallel(calls, _Ctx())
    assert len(results) == 1
    call, result, ms = results[0]
    assert result["ok"] is False
    assert "strict_violation" in result.get("error", "")
