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
        return {"mode": "chat", "status_label": "普通对话"}


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
