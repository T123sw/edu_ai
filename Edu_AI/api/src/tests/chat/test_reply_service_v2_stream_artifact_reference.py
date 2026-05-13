from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["message"]["content"]))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "workflow", "status_label": "completed"}


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


def test_reply_service_stream_routes_report_artifact_references_to_edit_runtime():
    calls = []
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])

    class DummyEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls.append(
                {
                    "question": request.question,
                    "artifact_id": request.artifact_reference.artifact_id,
                    "course_id": request.course_id,
                }
            )
            return {
                "message": {"role": "assistant", "content": "updated"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=StreamOrchestrator(),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="请把第 5 节改成更适合初一学生",
        conversation_id="conv-1",
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
            "version_id": "v1",
            "title": "report.md",
        },
    )

    events = list(service.reply_stream(payload))

    assert [event["type"] for event in events] == ["result", "done"]
    assert events[0]["payload"]["action"]["name"] == "report.edit"
    assert calls == [
        {
            "question": "请把第 5 节改成更适合初一学生",
            "artifact_id": "report-1",
            "course_id": "course-1",
        }
    ]
    assert store.saved == [("conv-1", "请把第 5 节改成更适合初一学生", "updated")]
