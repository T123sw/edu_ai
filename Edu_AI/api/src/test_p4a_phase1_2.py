"""P4-A Phase 1+2 validation tests.

Tests:
  T1 - plain chat response (no tool calls)
  T2 - tool call flow (generate_quiz stub)
  T3 - draft_outline → generate_report stub flow
  T4 - budget exceeded guard
  T5 - capability gate (rag_search blocked when allow_rag=False)
  T6 - fallback on unsupported
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_snapshot(allow_rag=False, allow_web=False):
    from app.chat.domain.capability_policy import CapabilityPolicy
    snap = MagicMock()
    snap.capability = CapabilityPolicy(allow_rag=allow_rag, allow_web=allow_web)
    snap.recent_messages = []
    return snap

def _make_request(question):
    req = MagicMock()
    req.question = question
    req.conversation_id = "conv-test"
    req.owner = "test-user"
    req.action_hint = None
    return req

def _text_event(content):
    return {"type": "text_delta", "content": content}

def _tool_calls_event(*calls):
    return {
        "type": "tool_calls",
        "calls": [{"id": f"call_{c['name']}", "name": c["name"], "args": c["args"]} for c in calls],
    }

def _done():
    return {"type": "done"}


# ── T1: plain chat ────────────────────────────────────────────────────────────

def test_plain_chat():
    from app.chat.runtime.react_agent import ReActAgent
    gw = MagicMock()
    gw.stream_chat_with_tools.return_value = [
        _text_event("量子纠缠"),
        _text_event("是量子力学中的一种现象。"),
        _done(),
    ]
    fast = MagicMock()
    agent = ReActAgent(agent_gateway=gw, fast_runtime=fast)
    events = list(agent.run_stream(request=_make_request("量子纠缠是什么"), snapshot=_make_snapshot()))

    types = [e["type"] for e in events]
    assert "delta" in types, f"期望有 delta 事件，实际: {types}"
    assert "result" in types, f"期望有 result 事件，实际: {types}"
    assert "task_submitted" not in types, "普通对话不应有 task_submitted"
    result_evt = next(e for e in events if e["type"] == "result")
    assert "量子纠缠" in result_evt["payload"]["message"]["content"]
    print("T1 PASS: plain chat → delta + result, no tool_submitted")


# ── T2: generate_quiz stub ────────────────────────────────────────────────────

def test_generate_quiz_stub():
    from app.chat.runtime.react_agent import ReActAgent
    gw = MagicMock()
    # First LLM call: decide to call generate_quiz
    gw.stream_chat_with_tools.side_effect = [
        [
            _tool_calls_event({"name": "generate_quiz", "args": {"subject": "Python基础", "question_count": 10}}),
            _done(),
        ],
        # Second LLM call after tool result: plain text confirmation
        [
            _text_event("练习题已提交，请稍候。"),
            _done(),
        ],
    ]
    agent = ReActAgent(agent_gateway=gw, fast_runtime=MagicMock())
    events = list(agent.run_stream(
        request=_make_request("出10道Python基础选择题"),
        snapshot=_make_snapshot(),
    ))

    types = [e["type"] for e in events]
    assert "task_submitted" in types, f"期望有 task_submitted，实际: {types}"
    ts = next(e for e in events if e["type"] == "task_submitted")
    task_id = ts["payload"]["task_id"]
    assert task_id, f"task_id 不能为空: {ts}"
    assert ts["payload"]["workflow_type"] == "quiz"
    print(f"T2 PASS: generate_quiz real handler → task_id={task_id}")


# ── T3: draft_outline → generate_report flow ─────────────────────────────────

def test_draft_outline_then_generate():
    from app.chat.runtime.react_agent import ReActAgent
    gw = MagicMock()
    # Turn 1: call draft_outline
    # Turn 2 (after outline shown): call generate_report
    # Turn 3 (after task submitted): confirmation text
    gw.stream_chat_with_tools.side_effect = [
        [
            _tool_calls_event({"name": "draft_outline", "args": {
                "resource_type": "report", "subject": "量子计算"
            }}),
            _done(),
        ],
        [
            _tool_calls_event({"name": "generate_report", "args": {
                "subject": "量子计算", "confirmed_outline": "# 一、引言\n# 二、原理\n# 三、应用"
            }}),
            _done(),
        ],
        [_text_event("报告生成任务已提交。"), _done()],
    ]
    # draft_outline calls gateway.chat()
    gw.chat.return_value = "# 一、引言\n# 二、原理\n# 三、应用"

    agent = ReActAgent(agent_gateway=gw, fast_runtime=MagicMock())
    events = list(agent.run_stream(
        request=_make_request("帮我写一份量子计算报告"),
        snapshot=_make_snapshot(),
    ))

    types = [e["type"] for e in events]
    assert "tool_call" in types
    tool_calls = [e["payload"]["tool"] for e in events if e["type"] == "tool_call"]
    assert "draft_outline" in tool_calls, f"期望调用 draft_outline，实际: {tool_calls}"
    assert "generate_report" in tool_calls, f"期望调用 generate_report，实际: {tool_calls}"
    assert "task_submitted" in types
    ts = next(e for e in events if e["type"] == "task_submitted")
    task_id = ts["payload"]["task_id"]
    assert task_id, f"task_id 不能为空: {ts}"
    assert ts["payload"]["workflow_type"] == "report"
    print(f"T3 PASS: draft_outline → generate_report real handler → task_id={task_id}")


# ── T4: budget guard ──────────────────────────────────────────────────────────

def test_budget_exceeded():
    from app.chat.runtime.agent_tools import execute_tool, ToolExecutionContext
    from app.chat.domain.capability_policy import CapabilityPolicy
    ctx = ToolExecutionContext(
        capability=CapabilityPolicy(allow_rag=True),
        max_steps=2,
    )
    ctx.step_count = 2  # already at limit
    result = execute_tool("rag_search", {"query": "test"}, ctx)
    assert result["ok"] is False
    assert result["error"] == "budget_exceeded"
    print("T4 PASS: budget_exceeded guard works")


# ── T5: capability gate ───────────────────────────────────────────────────────

def test_capability_gate():
    from app.chat.runtime.agent_tools import execute_tool, ToolExecutionContext
    from app.chat.domain.capability_policy import CapabilityPolicy
    ctx = ToolExecutionContext(
        capability=CapabilityPolicy(allow_rag=False),
        max_steps=4,
    )
    result = execute_tool("rag_search", {"query": "test"}, ctx)
    assert result["ok"] is False
    assert result["error"] == "permission_denied"
    print("T5 PASS: capability gate blocks rag_search when allow_rag=False")


# ── T6: fallback on unsupported ───────────────────────────────────────────────

def test_fallback_on_unsupported():
    from app.chat.runtime.react_agent import ReActAgent
    gw = MagicMock()
    gw.stream_chat_with_tools.return_value = [{"type": "unsupported"}]
    fast = MagicMock()
    fast.run_stream.return_value = iter([
        {"type": "delta", "payload": {"content": "fallback reply"}},
        {"type": "result", "payload": {"message": {"role": "assistant", "content": "fallback reply"}}},
    ])
    agent = ReActAgent(agent_gateway=gw, fast_runtime=fast)
    events = list(agent.run_stream(request=_make_request("test"), snapshot=_make_snapshot()))
    # fallback should have been called
    fast.run_stream.assert_called_once()
    print("T6 PASS: unsupported → fallback to fast_runtime")


# ── run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_plain_chat,
        test_generate_quiz_stub,
        test_draft_outline_then_generate,
        test_budget_exceeded,
        test_capability_gate,
        test_fallback_on_unsupported,
    ]
    failed = []
    for t in tests:
        try:
            t()
        except Exception as exc:
            print(f"FAIL {t.__name__}: {exc}")
            import traceback; traceback.print_exc()
            failed.append(t.__name__)

    print()
    if failed:
        print(f"FAILED {len(failed)} test(s): {failed}")
        sys.exit(1)
    else:
        print(f"ALL {len(tests)} TESTS PASSED")
