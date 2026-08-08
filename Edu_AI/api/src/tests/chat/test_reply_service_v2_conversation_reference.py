from types import SimpleNamespace

from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class DummyStorage:
    def __init__(self):
        self.messages = []
        self.state = {}

    def ensure_conversation(self, conversation_id, question=None, owner=None):
        return None

    def append_message(
        self, conversation_id, role, content, sources=None,
        message_kind=None, **_metadata,
    ):
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


def test_normalize_chat_request_preserves_conversation_reference():
    payload = SimpleNamespace(
        question="基于引用对话继续分析",
        conversation_id="conv-1",
        owner="u1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        action_hint=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        artifact_reference=None,
        conversation_reference={
            "conversation_id": "conv-ref-1",
            "title": "高一物理课堂观察",
            "message_count": 6,
        },
    )

    request = normalize_chat_request(payload)

    assert request.conversation_reference.model_dump(exclude_none=True) == {
        "conversation_id": "conv-ref-1",
        "title": "高一物理课堂观察",
        "message_count": 6,
    }


def test_write_v2_result_persists_conversation_reference():
    storage = DummyStorage()
    adapter = ConversationStoreAdapter(storage=storage)
    request = SimpleNamespace(
        question="基于引用对话继续分析",
        conversation_id="conv-1",
        course_id="course-1",
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
        artifact_reference=None,
        conversation_reference={
            "conversation_id": "conv-ref-1",
            "title": "高一物理课堂观察",
            "message_count": 6,
        },
    )
    result = {
        "message": {"content": "我结合引用对话继续分析如下。"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "chat.reply"},
        "workflow": None,
        "artifacts": [],
        "sources": [],
        "trace": {"path": "fast"},
    }

    adapter.write_v2_result("conv-1", request, result)

    assert storage.state["conversation_reference"]["conversation_id"] == "conv-ref-1"
    assert storage.state["active_context"]["active_reference_mode"] == "conversation_reference"
    assert storage.state["active_context"]["referenced_conversation_id"] == "conv-ref-1"
