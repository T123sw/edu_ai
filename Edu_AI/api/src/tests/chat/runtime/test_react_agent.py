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
    capability = SimpleNamespace(
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
    )
    request = SimpleNamespace(
        question="hello",
        conversation_id="conv-1",
        owner="teacher-a",
        course_id="course-1",
        scope_type="course",
        scope_id=None,
    )
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)
    return request, snapshot


def test_react_agent_streams_plain_text_and_final_result():
    request, snapshot = _request_snapshot()
    agent = ReActAgent(agent_gateway=FakeTextGateway(), fast_runtime=FakeFastRuntime(), max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert [event["type"] for event in events] == ["status", "delta", "delta", "result"]
    assert events[-1]["payload"]["message"]["content"] == "你好，可以。"
    assert events[-1]["payload"]["trace"]["path"] == "agent"


def test_react_agent_forces_selected_document_rag_before_plain_answer():
    seen = {}

    def rag_retriever(*, query, top_k, selected_doc_ids, owner):
        seen.update(
            query=query,
            top_k=top_k,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        return {
            "ok": True,
            "payload": {
                "answer": "冒泡排序会反复交换相邻逆序元素。",
                "sources": [{"document_id": "doc-1", "title": "冒泡排序资料"}],
            },
        }

    request, snapshot = _request_snapshot()
    request.question = "冒泡排序的原理"
    snapshot.capability.allow_rag = True
    snapshot.capability.selected_doc_ids = ["doc-1"]
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=FakeFastRuntime(),
        rag_retriever=rag_retriever,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert seen == {
        "query": "冒泡排序的原理",
        "top_k": 5,
        "selected_doc_ids": ["doc-1"],
        "owner": "teacher-a",
    }
    assert [event["type"] for event in events].count("tool_call") == 1
    assert next(event for event in events if event["type"] == "tool_call")["payload"]["tool"] == "rag_search"
    assert events[-1]["payload"]["sources"] == [
        {"document_id": "doc-1", "title": "冒泡排序资料"}
    ]
    assert events[-1]["payload"]["trace"]["source_mode"] == "selected_documents"


def test_react_agent_forces_rag_and_web_when_both_are_enabled():
    calls = []

    def rag_retriever(*, query, top_k, selected_doc_ids, owner):
        calls.append(("rag_search", query, list(selected_doc_ids)))
        return {
            "ok": True,
            "payload": {
                "answer": "知识库答案",
                "sources": [{"document_id": "doc-1", "title": "课程资料"}],
            },
        }

    def web_retriever(*, query, owner):
        calls.append(("web_search", query, owner))
        return {
            "ok": True,
            "payload": {
                "summary": "网络答案",
                "sources": [{"url": "https://example.com/source", "title": "网络来源"}],
            },
        }

    request, snapshot = _request_snapshot()
    snapshot.capability.allow_rag = True
    snapshot.capability.allow_web = True
    snapshot.capability.selected_doc_ids = ["doc-1", "doc-2"]
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=FakeFastRuntime(),
        rag_retriever=rag_retriever,
        web_retriever=web_retriever,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert [call[0] for call in calls] == ["rag_search", "web_search"]
    assert [
        event["payload"]["tool"]
        for event in events
        if event["type"] == "tool_call"
    ] == ["rag_search", "web_search"]
    assert events[-1]["payload"]["sources"] == [
        {"document_id": "doc-1", "title": "课程资料"},
        {"url": "https://example.com/source", "title": "网络来源"},
    ]


def test_react_agent_fails_closed_when_required_rag_has_no_evidence():
    def rag_retriever(*, query, top_k, selected_doc_ids, owner):
        return {
            "ok": True,
            "payload": {
                "answer": "",
                "sources": [],
            },
        }

    request, snapshot = _request_snapshot()
    request.question = "课程资料里的唯一事实是什么"
    snapshot.capability.allow_rag = True
    snapshot.capability.selected_doc_ids = ["doc-empty"]
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=FakeFastRuntime(),
        rag_retriever=rag_retriever,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    result = events[-1]["payload"]
    assert result["action"]["name"] == "agent.retrieval_incomplete"
    assert "未找到" in result["message"]["content"]
    assert result["sources"] == []


def test_react_agent_executes_generate_tool_and_emits_task_submitted(
    monkeypatch,
):
    class CommandService:
        def submit(self, command):
            return SimpleNamespace(edu_job_id="job-quiz-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.quiz.generation_command_service",
        CommandService(),
    )
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
