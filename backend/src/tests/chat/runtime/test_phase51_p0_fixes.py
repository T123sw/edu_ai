"""Phase 5.1 P0/P1 fix regression tests.

Covers:
- #1 State pollution: initial_input resets plan/reflect transient state
- #3 SqliteSaver removed: builder uses MemorySaver only
- #4 Message accumulation: injected system hints don't persist into state["messages"]
- #6 Abort termination: reflect verdict 'abort' routes to END + emits result
"""
import inspect


# ─── #1 State pollution: initial_input must reset all transient plan/reflect fields ──

def test_initial_input_resets_plan_state():
    from app.chat.runtime.react_agent import ReActAgent

    source = inspect.getsource(ReActAgent.run_stream)
    # All transient state fields must be reset explicitly
    for key in (
        '"current_plan": {}',
        '"plan_step_index": 0',
        '"plan_mode": ""',
        '"reflect_verdict": ""',
        '"reflect_hint": ""',
        '"reflect_filtered": {}',
        '"retry_counts": {}',
        '"last_tool_results": []',
    ):
        assert key in source, f"missing reset of {key} in initial_input"


# ─── #3 SqliteSaver: builder uses MemorySaver, no SQLite fallback path ────────

def test_builder_uses_memory_saver_only():
    from app.chat.runtime.graph import builder

    source = inspect.getsource(builder._build_checkpointer)
    assert "MemorySaver" in source
    assert "SqliteSaver" not in source, "SqliteSaver code path should be removed"


# ─── #4 Message accumulation: executor persists state["messages"] not local messages ──

def test_executor_returns_use_original_state_messages():
    """Both return paths of executor_node should use state['messages'], not the
    locally-mutated `messages` (which has injected reflect/plan_step hints)."""
    from app.chat.runtime.nodes import executor as ex_mod

    source = inspect.getsource(ex_mod.executor_node)

    # Look for both return statements that add messages
    # Path 1: tool_calls branch
    assert 'state["messages"] + [assistant_msg]' in source, \
        "tool-call return path should persist state['messages'] + assistant_msg"

    # Path 2: final answer branch
    assert 'state["messages"] + [{"role": "assistant", "content": answer}]' in source, \
        "final-answer return path should persist state['messages'] + final assistant msg"


# ─── #6 Abort termination ─────────────────────────────────────────────────────

def test_route_after_reflect_abort_returns_END():
    from langgraph.graph import END
    from app.chat.runtime.graph.routes import route_after_reflect

    assert route_after_reflect({"reflect_verdict": "abort"}) == END
    assert route_after_reflect({"reflect_verdict": "replan"}) == "planner"
    assert route_after_reflect({"reflect_verdict": "retry"}) == "executor"
    assert route_after_reflect({"reflect_verdict": "pass"}) == "executor"
    assert route_after_reflect({"reflect_verdict": ""}) == "executor"


def test_graph_builder_wires_END_for_abort():
    """Verify the graph compiles with END as a valid post-reflect destination."""
    from app.chat.runtime.graph import builder

    source = inspect.getsource(builder.build_graph)
    # The route mapping must include END
    assert "END: END" in source or "END:END" in source.replace(" ", "")


def test_emit_abort_result_appends_assistant_message():
    """_emit_abort_result should append a user-facing assistant message to messages."""
    from app.chat.runtime.nodes import reflect as reflect_mod

    captured = []

    class _W:
        def __call__(self, e): captured.append(e)

    state = {
        "messages": [{"role": "user", "content": "原问题"}],
        "tool_exchange": [],
    }
    updates: dict = {}

    # _emit_abort_result tries get_config; patch it to fail so conv_id falls back to ""
    import langgraph.config as lc
    original = lc.get_config

    def _raise(*args, **kw):
        raise RuntimeError("not in graph context")

    lc.get_config = _raise
    try:
        reflect_mod._emit_abort_result(_W(), state, "测试中止原因", updates)
    finally:
        lc.get_config = original

    # Should have emitted a result event
    result_events = [e for e in captured if e.get("type") == "result"]
    assert len(result_events) == 1
    payload = result_events[0]["payload"]
    assert payload["action"]["name"] == "agent.aborted"
    assert "测试中止原因" in payload["message"]["content"]

    # Should have appended the assistant message to updates["messages"]
    assert "messages" in updates
    last = updates["messages"][-1]
    assert last["role"] == "assistant"
    assert "测试中止原因" in last["content"]
