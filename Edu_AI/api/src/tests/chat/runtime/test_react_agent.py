from types import SimpleNamespace

from app.chat.runtime.react_agent import ReActAgent


class FakeTextGateway:
    def stream_chat_with_tools(self, messages, tools, tool_choice="auto", temperature=0.1, max_tokens=1024):
        yield {"type": "text_delta", "content": "你好"}
        yield {"type": "text_delta", "content": "，可以。"}
        yield {"type": "done"}


class FakeToolGateway:
    def __init__(self):
        self.calls = 0

    def stream_chat_with_tools(self, messages, tools, tool_choice="auto", temperature=0.1, max_tokens=1024):
        self.calls += 1
        if self.calls == 1:
            yield {
                "type": "tool_calls",
                "calls": [
                    {
                        "id": "call-quiz",
                        "name": "generate_quiz",
                        "args": {"subject": "Python basics"},
                    }
                ],
            }
            yield {"type": "done"}
            return
        yield {"type": "text_delta", "content": "练习题任务已提交。"}
        yield {"type": "done"}


class FakeFastRuntime:
    def run_stream(self, *, request, snapshot, decision):
        yield {"type": "delta", "payload": {"content": f"fallback:{decision.reason}"}}
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": "fallback"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            },
        }


def _request_snapshot():
    capability = SimpleNamespace(allow_rag=False, allow_web=False)
    request = SimpleNamespace(question="hello", conversation_id="conv-1")
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)
    return request, snapshot


def test_react_agent_streams_plain_text_and_final_result():
    request, snapshot = _request_snapshot()
    agent = ReActAgent(agent_gateway=FakeTextGateway(), fast_runtime=FakeFastRuntime(), max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert [event["type"] for event in events] == ["status", "delta", "delta", "result"]
    assert events[-1]["payload"]["message"]["content"] == "你好，可以。"
    assert events[-1]["payload"]["trace"]["path"] == "agent"


def test_react_agent_executes_generate_tool_and_emits_task_submitted():
    request, snapshot = _request_snapshot()
    agent = ReActAgent(agent_gateway=FakeToolGateway(), fast_runtime=FakeFastRuntime(), max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert [event["type"] for event in events] == [
        "status",
        "tool_call",
        "tool_result",
        "task_submitted",
        "delta",
        "result",
    ]
    task_payload = events[3]["payload"]
    assert task_payload["workflow_type"] == "quiz"
    assert task_payload["task_id"]
    assert events[-1]["payload"]["trace"]["agent_steps"][0]["tool"] == "generate_quiz"


def test_react_agent_emits_plan_event_for_generation_request():
    """Phase 2-B: generation keywords trigger planner, which emits a 'plan' SSE event."""

    class FakePlannerGateway:
        def stream_chat_with_tools(self, messages, tools, tool_choice="auto", temperature=0.1, max_tokens=1024):
            yield {
                "type": "tool_calls",
                "calls": [{
                    "id": "call-plan",
                    "name": "create_plan",
                    "args": {
                        "subject": "Python基础",
                        "resource_type": "report",
                        "steps": [
                            {"index": 1, "user_title": "起草大纲", "internal_action": "draft_outline", "expected_tools": ["draft_outline"]},
                            {"index": 2, "user_title": "生成报告", "internal_action": "generate_resource", "expected_tools": ["generate_report"]},
                        ],
                    },
                }],
            }
            yield {"type": "done"}

    capability = SimpleNamespace(allow_rag=False, allow_web=False)
    request = SimpleNamespace(question="帮我生成Python基础报告", conversation_id="conv-plan-1")
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)

    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        planner_gateway=FakePlannerGateway(),
        fast_runtime=FakeFastRuntime(),
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))
    event_types = [e["type"] for e in events]

    assert "plan" in event_types, f"Expected 'plan' event, got: {event_types}"
    plan_event = next(e for e in events if e["type"] == "plan")
    assert plan_event["payload"]["subject"] == "Python基础"
    assert len(plan_event["payload"]["steps"]) == 2
    assert plan_event["payload"]["steps"][0]["user_title"] == "起草大纲"


def test_react_agent_falls_back_when_gateway_lacks_tool_streaming():
    request, snapshot = _request_snapshot()
    agent = ReActAgent(agent_gateway=object(), fast_runtime=FakeFastRuntime(), max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert events[0]["type"] == "status"
    assert events[1]["type"] == "status"
    assert events[2]["type"] == "delta"
    assert events[2]["payload"]["content"] == "fallback:gateway_no_tools_support"
