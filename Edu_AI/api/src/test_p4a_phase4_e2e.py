"""P4-A Phase 4 — end-to-end verification.

Two modes:
  python test_p4a_phase4_e2e.py          → mock mode (no server needed)
  python test_p4a_phase4_e2e.py --live   → live mode (requires server on :8001)

Mock tests (always run):
  M1  plain chat        → delta stream, no task_submitted
  M2  generate_quiz     → real handler called, real task_id (UUID)
  M3  draft_outline → generate_report full flow
  M4  rag_search capability gate
  M5  agent fallback on LLM error
  M6  outline_parser correctness
  M7  ppt slide role assignment (title/content/summary)
  M8  budget exceeded mid-flow

Live tests (--live only):
  L1  POST /api/chat/v2/stream plain chat → SSE delta events
  L2  POST /api/chat/v2/stream "出10道Python题" → task_submitted event
  L3  GET  /api/chat/tasks/{task_id}      → task status queryable
  L4  action_hint path not affected       → no [AGENT] in logs
"""
from __future__ import annotations

import json
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))

LIVE_MODE = "--live" in sys.argv
BASE_URL = "http://localhost:8001"
PASS = []
FAIL = []


def ok(label: str):
    PASS.append(label)
    print(f"  PASS  {label}")


def fail(label: str, reason: str):
    FAIL.append(label)
    print(f"  FAIL  {label}: {reason}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_snapshot(allow_rag=False, allow_web=False):
    from unittest.mock import MagicMock
    from app.chat.domain.capability_policy import CapabilityPolicy
    snap = MagicMock()
    snap.capability = CapabilityPolicy(allow_rag=allow_rag, allow_web=allow_web)
    snap.recent_messages = []
    return snap


def _make_request(question, action_hint=None):
    from unittest.mock import MagicMock
    req = MagicMock()
    req.question = question
    req.conversation_id = f"test-{uuid.uuid4().hex[:8]}"
    req.owner = "test-user"
    req.action_hint = action_hint
    return req


def _text(content):
    return {"type": "text_delta", "content": content}


def _tool_call(name, args):
    return {
        "type": "tool_calls",
        "calls": [{"id": f"call_{name}", "name": name, "args": args}],
    }


def _done():
    return {"type": "done"}


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Mock tests
# ─────────────────────────────────────────────────────────────────────────────

def _run_mock_tests():
    from unittest.mock import MagicMock
    from app.chat.runtime.react_agent import ReActAgent

    print("\n── Mock Tests ──────────────────────────────────────────────────")

    # M1: plain chat
    try:
        gw = MagicMock()
        gw.stream_chat_with_tools.return_value = [
            _text("量子纠缠是量子力学现象。"), _done()
        ]
        events = list(ReActAgent(agent_gateway=gw, fast_runtime=MagicMock()).run_stream(
            request=_make_request("量子纠缠"), snapshot=_make_snapshot()))
        types = [e["type"] for e in events]
        assert "delta" in types and "result" in types and "task_submitted" not in types
        ok("M1  plain chat → delta+result, no task_submitted")
    except Exception as e:
        fail("M1  plain chat", str(e))

    # M2: generate_quiz — real handler, UUID task_id
    try:
        gw = MagicMock()
        gw.stream_chat_with_tools.side_effect = [
            [_tool_call("generate_quiz", {"subject": "Python基础", "question_count": 5}), _done()],
            [_text("练习题任务已提交。"), _done()],
        ]
        events = list(ReActAgent(agent_gateway=gw, fast_runtime=MagicMock()).run_stream(
            request=_make_request("出5道Python题"), snapshot=_make_snapshot()))
        ts = next((e for e in events if e["type"] == "task_submitted"), None)
        assert ts, "没有 task_submitted 事件"
        assert _is_uuid(ts["payload"]["task_id"]), f"task_id 不是 UUID: {ts['payload']['task_id']}"
        assert ts["payload"]["workflow_type"] == "quiz"
        ok(f"M2  generate_quiz real → UUID task_id={ts['payload']['task_id'][:8]}...")
    except Exception as e:
        fail("M2  generate_quiz real handler", str(e))

    # M3: draft_outline → generate_report
    try:
        gw = MagicMock()
        gw.chat.return_value = "# 一、引言\n## 背景\n# 二、方法\n## 核心算法"
        gw.stream_chat_with_tools.side_effect = [
            [_tool_call("draft_outline", {"resource_type": "report", "subject": "机器学习"}), _done()],
            [_tool_call("generate_report", {"subject": "机器学习", "confirmed_outline": "# 一、引言\n# 二、方法"}), _done()],
            [_text("报告已提交后台生成。"), _done()],
        ]
        events = list(ReActAgent(agent_gateway=gw, fast_runtime=MagicMock()).run_stream(
            request=_make_request("写一份机器学习报告"), snapshot=_make_snapshot()))
        tool_calls = [e["payload"]["tool"] for e in events if e["type"] == "tool_call"]
        assert "draft_outline" in tool_calls, f"缺少 draft_outline: {tool_calls}"
        assert "generate_report" in tool_calls, f"缺少 generate_report: {tool_calls}"
        ts = next((e for e in events if e["type"] == "task_submitted"), None)
        assert ts and _is_uuid(ts["payload"]["task_id"])
        assert ts["payload"]["workflow_type"] == "report"
        ok(f"M3  draft_outline→generate_report → task_id={ts['payload']['task_id'][:8]}...")
    except Exception as e:
        fail("M3  draft_outline→generate_report", str(e))

    # M4: rag_search blocked when allow_rag=False
    try:
        from app.chat.runtime.agent_tools import execute_tool, ToolExecutionContext
        from app.chat.domain.capability_policy import CapabilityPolicy
        ctx = ToolExecutionContext(capability=CapabilityPolicy(allow_rag=False), max_steps=4)
        result = execute_tool("rag_search", {"query": "test"}, ctx)
        assert not result["ok"] and result["error"] == "permission_denied"
        ok("M4  rag_search blocked (allow_rag=False)")
    except Exception as e:
        fail("M4  capability gate", str(e))

    # M5: fallback on LLM error
    try:
        gw = MagicMock()
        gw.stream_chat_with_tools.return_value = [{"type": "error", "message": "API timeout"}]
        fast = MagicMock()
        fast.run_stream.return_value = iter([
            {"type": "delta", "payload": {"content": "fallback"}},
            {"type": "result", "payload": {"message": {"role": "assistant", "content": "fallback"}}},
        ])
        events = list(ReActAgent(agent_gateway=gw, fast_runtime=fast).run_stream(
            request=_make_request("test"), snapshot=_make_snapshot()))
        fast.run_stream.assert_called_once()
        ok("M5  LLM error → fallback to fast_runtime")
    except Exception as e:
        fail("M5  fallback on error", str(e))

    # M6: outline_parser
    try:
        from app.chat.runtime.agent_tools.handlers.outline_parser import (
            parse_report_outline, parse_ppt_slides
        )
        ch = parse_report_outline("# 第一章\n## 节一\n## 节二\n# 第二章\n## 节三")
        assert ch and len(ch) == 2 and len(ch[0]["sections"]) == 2
        sl = parse_ppt_slides("## 封面\n- 要点A\n## 内容\n- 要点B\n## 总结")
        assert sl and len(sl) == 3 and sl[1]["bullets"] == ["要点B"]
        assert parse_report_outline("") is None
        assert parse_ppt_slides("无标题内容") is None
        ok("M6  outline_parser: chapters / slides / empty fallback")
    except Exception as e:
        fail("M6  outline_parser", str(e))

    # M7: PPT slide role assignment
    try:
        from app.chat.runtime.agent_tools.handlers.ppt import _build_ppt_slides
        raw = [{"title": "封面", "bullets": []},
               {"title": "内容A", "bullets": ["点1"]},
               {"title": "内容B", "bullets": ["点2"]},
               {"title": "总结", "bullets": []}]
        slides = _build_ppt_slides(raw)
        assert slides[0].role == "title"
        assert slides[1].role == "content"
        assert slides[2].role == "content"
        assert slides[3].role == "summary"
        ok("M7  PPT slide roles: title/content/content/summary")
    except Exception as e:
        fail("M7  PPT slide roles", str(e))

    # M8: budget exceeded mid-flow
    try:
        from app.chat.runtime.agent_tools import execute_tool, ToolExecutionContext
        from app.chat.domain.capability_policy import CapabilityPolicy
        ctx = ToolExecutionContext(capability=CapabilityPolicy(), max_steps=2)
        ctx.step_count = 2
        result = execute_tool("generate_quiz", {"subject": "test"}, ctx)
        assert not result["ok"] and result["error"] == "budget_exceeded"
        ok("M8  budget_exceeded blocks generate_quiz at max_steps")
    except Exception as e:
        fail("M8  budget exceeded", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Live tests (require running server)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if data and data != "[DONE]":
                try:
                    events.append(json.loads(data))
                except json.JSONDecodeError:
                    pass
    return events


def _get_live_token() -> str:
    """Obtain a bearer token via /api/auth/login (admin/admin123 default)."""
    import requests
    username = os.environ.get("LIVE_TEST_USER", "admin")
    password = os.environ.get("LIVE_TEST_PASS", "admin123")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("token", "")
    except Exception as e:
        print(f"  [warn] 获取 token 失败: {e}")
        return ""


def _run_live_tests():
    import requests

    print(f"\n── Live Tests (server: {BASE_URL}) ─────────────────────────────")

    token = _get_live_token()
    auth_headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    }

    # L1: plain chat — SSE delta events
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat/v2/stream",
            json={"question": "用一句话解释量子纠缠", "conversation_id": f"live-{uuid.uuid4().hex[:6]}"},
            headers=auth_headers,
            stream=True, timeout=30,
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        raw = resp.text
        events = _parse_sse(raw)
        types = [e.get("type") for e in events]
        assert "delta" in types or any(
            isinstance(e.get("payload"), dict) and e["payload"].get("content") for e in events
        ), f"没有 delta 事件: {types}"
        ok(f"L1  plain chat SSE → {len(events)} events, types={list(dict.fromkeys(types))}")
    except Exception as e:
        fail("L1  plain chat live", str(e))

    # L2: generate_quiz — should get task_submitted
    try:
        conv_id = f"live-quiz-{uuid.uuid4().hex[:6]}"
        resp = requests.post(
            f"{BASE_URL}/api/chat/v2/stream",
            json={"question": "出5道Python基础单选题", "conversation_id": conv_id},
            headers=auth_headers,
            stream=True, timeout=60,
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        events = _parse_sse(resp.text)
        ts_events = [e for e in events if e.get("type") == "task_submitted"]
        if ts_events:
            task_id = ts_events[0].get("payload", {}).get("task_id", "")
            assert _is_uuid(task_id), f"task_id 不是 UUID: {task_id}"
            ok(f"L2  generate_quiz → task_submitted task_id={task_id[:8]}...")

            # L3: query task status
            try:
                status_resp = requests.get(
                    f"{BASE_URL}/api/chat/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                    timeout=10,
                )
                assert status_resp.status_code == 200
                status_data = status_resp.json()
                assert "status" in status_data
                ok(f"L3  GET /tasks/{task_id[:8]}... → status={status_data['status']}")
            except Exception as e2:
                fail("L3  task status query", str(e2))
        else:
            types = list(dict.fromkeys(e.get("type") for e in events))
            fail("L2  generate_quiz", f"没有 task_submitted 事件，实际 types={types}")
    except Exception as e:
        fail("L2  generate_quiz live", str(e))

    # L4: action_hint path bypasses agent
    try:
        conv_id = f"live-hint-{uuid.uuid4().hex[:6]}"
        resp = requests.post(
            f"{BASE_URL}/api/chat/v2/stream",
            json={
                "question": "帮我生成报告",
                "conversation_id": conv_id,
                "action_hint": "generate.report",
            },
            headers=auth_headers,
            stream=True, timeout=30,
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        events = _parse_sse(resp.text)
        types = list(dict.fromkeys(e.get("type") for e in events))
        # Should get task_submitted via workflow path, not agent thinking status
        thinking = any(
            e.get("type") == "status" and
            isinstance(e.get("payload"), dict) and
            e["payload"].get("stage") == "thinking"
            for e in events
        )
        assert not thinking, "action_hint 路径不应进入 agent thinking"
        ok(f"L4  action_hint bypasses agent → types={types}")
    except Exception as e:
        fail("L4  action_hint bypass", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(f"P4-A Phase 4 E2E  |  mode={'LIVE' if LIVE_MODE else 'MOCK'}")
    print("=" * 60)

    _run_mock_tests()

    if LIVE_MODE:
        _run_live_tests()
    else:
        print("\n(skip live tests — run with --live to test against server)")

    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}   FAILED: {len(FAIL)}")
    if FAIL:
        print("FAILED tests:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
