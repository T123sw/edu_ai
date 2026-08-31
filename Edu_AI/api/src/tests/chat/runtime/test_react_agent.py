from types import SimpleNamespace

from app.chat.persistence.agent_run_store import AgentRunStore
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
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


class DirectChatGateway:
    def __init__(self, answer="正常回答"):
        self.answer = answer
        self.messages = []

    def stream_chat(self, messages):
        self.messages = messages
        yield self.answer


class FakeFastRuntime:
    def __init__(self):
        self.calls = []

    def run_stream(self, *, request, snapshot, decision):
        self.calls.append(
            {
                "question": request.question,
                "reason": decision.reason,
            }
        )
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
        capability=capability,
    )
    snapshot = SimpleNamespace(capability=capability, recent_messages=[], workflow_state=None)
    return request, snapshot


def test_react_agent_keeps_ordinary_question_inside_agent_runtime():
    request, snapshot = _request_snapshot()
    request.question = "链表如何实现"
    fast_runtime = FakeFastRuntime()
    agent = ReActAgent(agent_gateway=FakeTextGateway(), fast_runtime=fast_runtime, max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert events[0]["type"] == "status"
    assert events[-1]["payload"]["trace"]["path"] == "agent"
    assert events[-1]["payload"]["message"]["content"] == "你好，可以。"
    assert fast_runtime.calls == []


def test_react_agent_keeps_rag_question_inside_agent_runtime():
    request, snapshot = _request_snapshot()
    request.question = "链表如何实现"
    snapshot.capability.allow_rag = True
    snapshot.capability.selected_doc_ids = ["doc-linked-list"]
    fast_runtime = FakeFastRuntime()
    gateway = FakeTextGateway()
    agent = ReActAgent(
        agent_gateway=gateway,
        fast_runtime=fast_runtime,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert events[0]["type"] == "status"
    assert any(event["type"] == "plan" for event in events)
    assert events[-1]["payload"]["trace"]["path"] == "agent"
    assert fast_runtime.calls == []


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
    fast_runtime = FakeFastRuntime()
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=fast_runtime,
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
    assert any(event["type"] == "plan" for event in events)
    assert events[-1]["payload"]["sources"] == [
        {"document_id": "doc-1", "title": "冒泡排序资料"}
    ]
    assert events[-1]["payload"]["trace"]["source_mode"] == "selected_documents"
    assert fast_runtime.calls == []


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
    fast_runtime = FakeFastRuntime()
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=fast_runtime,
        rag_retriever=rag_retriever,
        web_retriever=web_retriever,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert [call[0] for call in calls] == ["rag_search", "web_search"]
    assert any(event["type"] == "plan" for event in events)
    assert events[-1]["payload"]["sources"] == [
        {"document_id": "doc-1", "title": "课程资料"},
        {"url": "https://example.com/source", "title": "网络来源"},
    ]
    assert fast_runtime.calls == []


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
    fast_runtime = FastChatRuntime(
        model_gateway=DirectChatGateway(),
        rag_retriever=rag_retriever,
    )
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=fast_runtime,
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
    request.question = "生成 Python 基础练习题"
    agent = ReActAgent(agent_gateway=FakeToolGateway(), fast_runtime=FakeFastRuntime(), max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    event_types = [event["type"] for event in events]
    assert event_types[0] == "status"
    assert "plan" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "task_submitted" in event_types
    assert event_types[-1] == "result"
    task_payload = next(
        event["payload"] for event in events if event["type"] == "task_submitted"
    )
    assert task_payload["workflow_type"] == "quiz"
    assert task_payload["task_id"]
    assert events[-1]["payload"]["trace"]["agent_steps"][0]["tool"] == "generate_quiz"


def test_react_agent_bare_start_submits_confirmed_report(monkeypatch, tmp_path):
    submitted_commands = []

    class CommandService:
        def submit(self, command):
            submitted_commands.append(command)
            return SimpleNamespace(edu_job_id="job-report-start-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.report.generation_command_service",
        CommandService(),
    )
    run_store = AgentRunStore(tmp_path / "agent_runs.db")
    request, snapshot = _request_snapshot()
    request.conversation_id = "conv-report-start-1"
    request.question = "开始"
    run_store.save(
        request.conversation_id,
        request.owner,
        request.course_id,
        {
            "active_draft_outline": {
                "resource_type": "report",
                "subject": "链表实现报告大纲",
                "outline_markdown": "# 链表实现报告大纲",
            }
        },
    )
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=FakeFastRuntime(),
        agent_run_store=run_store,
        max_steps=6,
        timeout_seconds=5,
    )

    try:
        events = list(agent.run_stream(request=request, snapshot=snapshot))
    finally:
        run_store.close()

    assert len(submitted_commands) == 1
    assert submitted_commands[0].resource_type == "report"
    assert (
        submitted_commands[0].config["confirmed_outline"]
        == "# 链表实现报告大纲"
    )
    submitted = next(event for event in events if event["type"] == "task_submitted")
    assert submitted["payload"]["task_id"] == "job-report-start-1"
    assert submitted["payload"]["workflow_type"] == "report"
    assert any(
        step.get("tool") == "generate_report" and step.get("ok")
        for step in events[-1]["payload"]["trace"]["agent_steps"]
    )


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
    assert plan_event["payload"]["template_id"] == "single_confirmable"
    assert plan_event["payload"]["steps"][0]["expected_tools"] == ["draft_outline"]


def test_ordinary_question_falls_back_only_when_agent_gateway_is_unavailable():
    request, snapshot = _request_snapshot()
    fast_runtime = FakeFastRuntime()
    agent = ReActAgent(agent_gateway=object(), fast_runtime=fast_runtime, max_steps=4, timeout_seconds=5)

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert events[0]["type"] == "status"
    assert [event["type"] for event in events[-2:]] == ["delta", "result"]
    assert events[-2]["payload"]["content"] == "fallback:gateway_no_tools_support"
    assert fast_runtime.calls == [
        {"question": "hello", "reason": "gateway_no_tools_support"}
    ]
