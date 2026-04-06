from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class DummyStorage:
    def __init__(self):
        self.messages = []
        self.state = {}

    def ensure_conversation(self, conversation_id, question=None, owner=None):
        return None

    def append_message(self, conversation_id, role, content, sources=None, message_kind=None):
        self.messages.append(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "sources": sources,
                "message_kind": message_kind,
            }
        )

    def get_state(self, conversation_id):
        return dict(self.state)

    def get_messages(self, conversation_id, limit=None):
        items = list(self.messages)
        if limit:
          return items[-limit:]
        return items

    def update_state(self, conversation_id, patch):
        self.state.update(patch)


def test_normalize_chat_request_preserves_artifact_reference():
    payload = SimpleNamespace(
        question="重写结论",
        conversation_id="conv-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "李白性格分析.md",
        },
    )

    request = normalize_chat_request(payload)

    assert request.artifact_reference.model_dump(exclude_none=True) == {
        "artifact_id": "report-1",
        "artifact_type": "report",
        "version_id": "v1",
        "title": "李白性格分析.md",
    }


def test_write_v2_result_persists_active_artifact_reference():
    storage = DummyStorage()
    adapter = ConversationStoreAdapter(storage=storage)
    request = SimpleNamespace(
        question="重写结论",
        conversation_id="conv-1",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "李白性格分析.md",
        },
    )
    result = {
        "message": {"content": "已生成，请在右侧查看。"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "report.edit"},
        "workflow": None,
        "artifacts": [],
        "sources": [],
        "trace": {"path": "fast"},
    }

    adapter.write_v2_result("conv-1", request, result)

    assert storage.state["active_artifact"]["artifact_id"] == "report-1"
    assert storage.state["active_context"]["active_artifact_id"] == "report-1"
    assert storage.state["active_context"]["active_artifact_type"] == "report"
    assert storage.state["active_context"]["active_reference_mode"] == "artifact_edit"
    assert storage.state["referenced_artifact_ids"] == ["report-1"]


def test_reply_service_prefers_report_edit_runtime_when_artifact_reference_present():
    calls = []

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
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "report.edit"},
                "workflow": {"type": "report", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: None),
        report_edit_runtime=DummyEditRuntime(),
        conversation_store=SimpleNamespace(write_v2_result=lambda conversation_id, request, result: None),
        context_builder=SimpleNamespace(build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "workflow", "status_label": "已完成"}),
        course_storage_manager=SimpleNamespace(),
    )
    payload = SimpleNamespace(
        question="保留结构，重写结论",
        conversation_id="conv-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference={
            "artifact_id": "report-1",
            "artifact_type": "report",
            "version_id": "v1",
            "title": "李白性格分析.md",
        },
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "report.edit"
    assert calls == [{"question": "保留结构，重写结论", "artifact_id": "report-1", "course_id": "course-1"}]
