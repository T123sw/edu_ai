from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class StreamOrchestrator:
    def dispatch_stream(self, request, on_workflow_complete=None):
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}
        yield {"type": "delta", "payload": {"content": "hello"}}
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": "hello"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            },
        }


class DummyStore:
    def __init__(self):
        self.saved = []
        self.storage = SimpleNamespace(get_state=lambda _conversation_id: {})

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["message"]["content"]))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "chat", "status_label": "普通对话"}


class FactoryJobService:
    def __init__(self):
        self.reservations = []
        self.failures = []

    def reserve_factory_request(self, **kwargs):
        self.reservations.append(kwargs)
        return SimpleNamespace(
            edu_job_id="job-preparing-graph",
            kind=SimpleNamespace(value="generate_graph"),
            step="preparing",
        )

    def fail_factory_reservation(self, job_id, **kwargs):
        self.failures.append((job_id, kwargs))


class FactoryStreamOrchestrator:
    def dispatch_stream(self, request, on_workflow_complete=None):
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id}}
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": "正在生成思维导图"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "generate.graph"},
                "workflow": {"type": "graph", "status": "running"},
                "task_id": request.factory_job_id,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "deepseek-harness"},
            },
        }


class FailedFactoryStreamOrchestrator:
    def dispatch_stream(self, request, on_workflow_complete=None):
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": "模型服务暂时不可用"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "agent.failed"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {
                    "path": "deepseek-harness",
                    "error": "provider_unavailable",
                },
            },
        }


def test_reply_service_stream_finalizes_result_and_writes_once():
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(
        orchestrator=StreamOrchestrator(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="hello",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    events = list(service.reply_stream(payload))

    assert [event["type"] for event in events] == ["metadata", "delta", "result", "done"]
    assert events[2]["payload"]["status_card"]["status_label"] == "普通对话"
    assert events[3]["payload"]["conversation_id"] == "conv-1"
    assert store.saved == [("conv-1", "hello", "hello")]


def test_generation_factory_stream_does_not_write_conversation_history():
    store = DummyStore()
    memory_calls = []
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(
        orchestrator=StreamOrchestrator(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        memory_writer=SimpleNamespace(persist_turn=lambda **kwargs: memory_calls.append(kwargs)),
    )
    payload = SimpleNamespace(
        question="直接生成报告",
        conversation_id=None,
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.report",
        entry_mode="generation_factory",
        owner="u1",
    )

    events = list(service.reply_stream(payload))

    assert events[-1]["type"] == "done"
    assert store.saved == []
    assert memory_calls == []


def test_generation_factory_stream_publishes_persisted_preparing_job_first():
    store = DummyStore()
    jobs = FactoryJobService()
    service = ReplyServiceV2(
        orchestrator=FactoryStreamOrchestrator(),
        conversation_store=store,
        generation_command_service=jobs,
    )
    payload = SimpleNamespace(
        question="生成一张递归思维导图",
        request_id="factory-graph-1",
        conversation_id=None,
        model_id=None,
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.graph",
        entry_mode="generation_factory",
        owner="u1",
    )

    events = list(service.reply_stream(payload))

    assert events[0] == {
        "type": "task_submitted",
        "payload": {
            "task_id": "job-preparing-graph",
            "workflow_type": "graph",
            "conversation_id": events[0]["payload"]["conversation_id"],
            "stage": "preparing",
        },
    }
    assert jobs.reservations[0]["resource_type"] == "graph"
    assert jobs.failures == []


def test_generation_factory_preparation_failure_updates_the_visible_job():
    jobs = FactoryJobService()
    service = ReplyServiceV2(
        orchestrator=FailedFactoryStreamOrchestrator(),
        conversation_store=DummyStore(),
        generation_command_service=jobs,
    )
    payload = SimpleNamespace(
        question="生成一张递归思维导图",
        request_id="factory-graph-failed",
        conversation_id=None,
        model_id=None,
        course_id="course-1",
        scope_type="course",
        scope_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.graph",
        entry_mode="generation_factory",
        owner="u1",
    )

    events = list(service.reply_stream(payload))

    assert events[0]["type"] == "task_submitted"
    assert jobs.failures == [
        (
            "job-preparing-graph",
            {
                "error_code": "PROVIDER_UNAVAILABLE",
                "error_message": "模型服务暂时不可用",
            },
        )
    ]
