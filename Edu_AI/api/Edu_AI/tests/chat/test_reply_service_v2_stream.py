from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class StreamOrchestrator:
    def dispatch_stream(self, request):
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

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["message"]["content"]))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "chat", "status_label": "\u666e\u901a\u5bf9\u8bdd"}


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
    assert events[2]["payload"]["status_card"]["status_label"] == "\u666e\u901a\u5bf9\u8bdd"
    assert events[3]["payload"]["conversation_id"] == "conv-1"
    assert store.saved == [("conv-1", "hello", "hello")]


def test_reply_service_stream_loads_artifact_context_for_ask_path():
    captured = {}
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])

    class ArtifactStreamOrchestrator:
        def dispatch_stream(self, request):
            captured["artifact_context"] = getattr(request, "artifact_context", None)
            yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}
            yield {
                "type": "result",
                "payload": {
                    "message": {"role": "assistant", "content": "artifact answer"},
                    "conversation": {"conversation_id": request.conversation_id},
                    "action": {"name": "chat.reply"},
                    "workflow": None,
                    "artifacts": [],
                    "sources": [],
                    "trace": {"path": "fast"},
                },
            }

    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
            "report": "# \u674e\u767d\u6027\u683c\u5206\u6790\n\n## \u6458\u8981\n\u539f\u6458\u8981\u3002",
        }
    )
    service = ReplyServiceV2(
        orchestrator=ArtifactStreamOrchestrator(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="\u8fd9\u4efd\u62a5\u544a\u7684\u6838\u5fc3\u89c2\u70b9\u662f\u4ec0\u4e48\uff1f",
        conversation_id="conv-stream-ask",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "\u674e\u767d\u6027\u683c\u5206\u6790.md",
        },
    )

    events = list(service.reply_stream(payload))

    assert [event["type"] for event in events] == ["metadata", "result", "done"]
    assert captured["artifact_context"]["artifact_type"] == "report"
    assert "## \u6458\u8981" in captured["artifact_context"]["context_text"]


def test_reply_service_stream_routes_explicit_artifact_edit_to_edit_runtime():
    calls = {"edit": [], "stream": []}
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])

    class UnexpectedStreamOrchestrator:
        def dispatch_stream(self, request):
            calls["stream"].append(request.question)
            yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls["edit"].append(request.question)
            return {
                "message": {"role": "assistant", "content": "\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u53f3\u4fa7\u67e5\u770b\u3002"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=UnexpectedStreamOrchestrator(),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba",
        conversation_id="conv-stream-edit",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "report.md",
        },
    )

    events = list(service.reply_stream(payload))

    assert [event["type"] for event in events] == ["result", "done"]
    assert events[0]["payload"]["action"]["name"] == "report.edit"
    assert calls["edit"] == ["\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba"]
    assert calls["stream"] == []


def test_reply_service_stream_returns_clarification_for_unclear_artifact_request():
    calls = {"edit": [], "stream": []}
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])

    class UnexpectedStreamOrchestrator:
        def dispatch_stream(self, request):
            calls["stream"].append(request.question)
            yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls["edit"].append(request.question)
            return {"message": {"role": "assistant", "content": "unexpected"}}

    service = ReplyServiceV2(
        orchestrator=UnexpectedStreamOrchestrator(),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
    )
    payload = SimpleNamespace(
        question="\u5e2e\u6211\u4f18\u5316\u4e00\u4e0b\u8fd9\u4e2a\u62a5\u544a",
        conversation_id="conv-stream-unclear",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "title": "report.md",
        },
    )

    events = list(service.reply_stream(payload))

    assert [event["type"] for event in events] == ["result", "done"]
    assert events[0]["payload"]["action"]["name"] == "chat.reply"
    assert "\u8bf7\u5148\u544a\u8bc9\u6211\u4f60\u60f3\u4fee\u6539\u54ea\u4e00\u90e8\u5206" in events[0]["payload"]["message"]["content"]
    assert calls["edit"] == []
    assert calls["stream"] == []
