"""Phase 5 tests: strict mode, ToolMeta, parallel execution."""
from types import SimpleNamespace
from unittest.mock import patch

from app.chat.runtime.agent_tools.schemas import (
    SCHEMA_DRAFT_OUTLINE,
    SCHEMA_GENERATE_REPORT,
    SCHEMA_IMAGE_SEARCH,
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


def test_filter_schemas_empty_expected_returns_none():
    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_WEB_SEARCH]
    filtered = filter_schemas_by_step(all_schemas, [])
    assert filtered == []


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


def test_executor_hides_mutating_tools_for_unplanned_qa_contract():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    schemas = [
        SCHEMA_RAG_SEARCH,
        SCHEMA_IMAGE_SEARCH,
        SCHEMA_DRAFT_OUTLINE,
        SCHEMA_GENERATE_REPORT,
    ]
    state = {
        "task_contract": {"intent": "qa"},
        "plan_mode": "",
        "current_plan": {},
    }

    filtered = _filter_tool_schemas_for_step(schemas, state)

    assert [item["function"]["name"] for item in filtered] == [
        "rag_search",
        "image_search",
    ]


def test_executor_keeps_expected_generation_tool_for_generation_contract():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    state = {
        "task_contract": {"intent": "confirm"},
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [{"expected_tools": ["generate_report"]}],
        },
    }

    filtered = _filter_tool_schemas_for_step(
        [SCHEMA_RAG_SEARCH, SCHEMA_GENERATE_REPORT], state
    )

    assert [item["function"]["name"] for item in filtered] == [
        "rag_search",
        "generate_report",
    ]


def test_executor_strict_empty_allowlist_exposes_no_tools_and_disables_tool_choice():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step, _tool_choice_for_step

    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_DRAFT_OUTLINE]
    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {"steps": [{"index": 0, "expected_tools": []}]},
    }
    filtered = _filter_tool_schemas_for_step(all_schemas, state)
    assert filtered == []
    assert _tool_choice_for_step(state, filtered) == "none"


def test_tool_free_step_flattens_prior_function_protocol_to_read_only_context():
    from app.chat.runtime.nodes.executor import _prepare_tool_free_messages

    messages = [
        {"role": "system", "content": "教师助手"},
        {"role": "user", "content": "解释链表"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call-1", "function": {"name": "rag_search"}}],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "课程证据"},
    ]

    prepared = _prepare_tool_free_messages(messages)

    assert all(not item.get("tool_calls") for item in prepared)
    assert all(item.get("role") != "tool" for item in prepared)
    assert any("课程证据" in item.get("content", "") for item in prepared)
    assert "不授予任何工具权限" in prepared[-1]["content"]


def test_strict_single_tool_step_is_compiled_without_model_choice():
    from types import SimpleNamespace

    from app.chat.runtime.nodes.executor import _build_mandatory_plan_calls

    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {
            "subject": "快速排序",
            "resource_type": "classroom",
            "contract": {
                "topic": "快速排序",
                "resource_types": ["classroom"],
                "audience": "高一学生",
                "lesson_duration": 30,
                "constraints": {},
            },
            "steps": [
                {"internal_action": "draft_outline", "expected_tools": ["draft_outline"]}
            ],
        },
    }
    ctx = SimpleNamespace(trace={"agent_steps": []})

    calls = _build_mandatory_plan_calls(state, {}, ctx)

    assert calls == [
        {
            "id": "compiled_step_1_draft_outline",
            "name": "draft_outline",
            "args": {
                "subject": "快速排序",
                "resource_type": "classroom",
                "constraints": "{}",
                "audience": "高一学生",
                "duration_minutes": 30,
            },
        }
    ]


def test_compiled_classroom_uses_classroom_default_duration():
    from types import SimpleNamespace

    from app.chat.runtime.nodes.executor import _build_mandatory_plan_calls

    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {
            "subject": "快速排序",
            "resource_type": "classroom",
            "contract": {"topic": "快速排序", "resource_types": ["classroom"]},
            "steps": [{"expected_tools": ["generate_classroom"]}],
        },
    }

    calls = _build_mandatory_plan_calls(
        state, {}, SimpleNamespace(trace={"agent_steps": []})
    )

    assert calls[0]["args"]["duration_minutes"] == 25


def test_compiled_step_does_not_repeat_a_successful_tool():
    from types import SimpleNamespace

    from app.chat.runtime.nodes.executor import _build_mandatory_plan_calls

    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {
            "subject": "快速排序",
            "steps": [{"expected_tools": ["generate_report"]}],
        },
    }
    ctx = SimpleNamespace(
        trace={"agent_steps": [{"tool": "generate_report", "ok": True}]}
    )

    assert _build_mandatory_plan_calls(state, {}, ctx) == []


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


def test_executor_guided_mode_hides_generation_until_expected_step():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    all_schemas = [SCHEMA_RAG_SEARCH, SCHEMA_DRAFT_OUTLINE, SCHEMA_GENERATE_REPORT]
    state = {
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [
                {
                    "index": 0,
                    "internal_action": "draft_outline",
                    "expected_tools": ["draft_outline"],
                }
            ]
        },
    }

    filtered = _filter_tool_schemas_for_step(all_schemas, state)

    assert [schema["function"]["name"] for schema in filtered] == [
        "rag_search",
        "draft_outline",
    ]


def test_executor_hides_image_search_from_ordinary_answer_step():
    from app.chat.runtime.nodes.executor import _filter_unrequested_image_search

    schemas = [SCHEMA_RAG_SEARCH, SCHEMA_IMAGE_SEARCH]
    state = {
        "plan_step_index": 1,
        "current_plan": {
            "steps": [
                {"internal_action": "retrieve_context", "expected_tools": ["rag_search"]},
                {"internal_action": "answer_question", "expected_tools": []},
            ]
        },
    }

    filtered = _filter_unrequested_image_search(
        schemas,
        state,
        SimpleNamespace(question="请根据知识库概括问题分解与算法设计的关系"),
    )

    assert [schema["function"]["name"] for schema in filtered] == ["rag_search"]


def test_executor_keeps_image_search_for_visual_plan_step():
    from app.chat.runtime.nodes.executor import _filter_unrequested_image_search

    state = {
        "plan_step_index": 0,
        "current_plan": {
            "steps": [
                {
                    "internal_action": "fetch_visuals",
                    "expected_tools": ["image_search"],
                }
            ]
        },
    }

    filtered = _filter_unrequested_image_search(
        [SCHEMA_IMAGE_SEARCH],
        state,
        SimpleNamespace(question="继续生成"),
    )

    assert filtered == [SCHEMA_IMAGE_SEARCH]


def test_executor_keeps_image_search_for_explicit_visual_question_without_plan():
    from app.chat.runtime.nodes.executor import _filter_unrequested_image_search

    filtered = _filter_unrequested_image_search(
        [SCHEMA_IMAGE_SEARCH],
        {},
        SimpleNamespace(question="请给链表实现配一张结构图"),
    )

    assert filtered == [SCHEMA_IMAGE_SEARCH]


def test_executor_hides_successful_retrieval_tool_before_final_answer():
    from app.chat.runtime.nodes.executor import _filter_completed_retrieval_tools

    ctx = SimpleNamespace(
        trace={
            "agent_steps": [
                {"tool": "rag_search", "ok": True, "evidence_count": 5}
            ]
        }
    )

    filtered = _filter_completed_retrieval_tools(
        [SCHEMA_RAG_SEARCH, SCHEMA_WEB_SEARCH],
        ctx,
    )

    assert [schema["function"]["name"] for schema in filtered] == ["web_search"]


def test_executor_allows_finalization_grace_only_after_all_required_retrievals():
    from app.chat.runtime.nodes.executor import _required_retrieval_satisfied

    ctx = SimpleNamespace(
        capability=SimpleNamespace(allow_rag=True, allow_web=True),
        trace={
            "agent_steps": [
                {"tool": "rag_search", "ok": True, "evidence_count": 5},
                {"tool": "web_search", "ok": True, "evidence_count": 3},
            ]
        },
    )
    assert _required_retrieval_satisfied(ctx) is True

    ctx.trace["agent_steps"][1]["evidence_count"] = 0
    assert _required_retrieval_satisfied(ctx) is False


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


def test_enforce_strict_mode_rejects_every_call_for_empty_allowlist():
    from app.chat.runtime.nodes.tools import _enforce_strict_mode

    state = {
        "plan_mode": "strict",
        "plan_step_index": 0,
        "current_plan": {"steps": [{"index": 0, "expected_tools": []}]},
    }
    out = _enforce_strict_mode([{"id": "1", "name": "generate_report", "args": {}}], state)
    assert "strict模式" in out[0]["_rejected_reason"]


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
