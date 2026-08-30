from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.memory.domain import MemoryWriteResult


class _Store:
    def __init__(self):
        self.writes = []

    def write_v2_result(self, conversation_id, request, result):
        self.writes.append((conversation_id, request, result))


class _Writer:
    def __init__(self):
        self.calls = []

    def persist_turn(self, **kwargs):
        self.calls.append(kwargs)
        return MemoryWriteResult(
            candidate_count=1,
            accepted_count=1,
            written_count=1,
            provider="rules",
            provider_status="scheduled",
            memory_ids=["mem-1"],
        )


class _Orchestrator:
    def dispatch(self, request):
        return {
            "message": {"role": "assistant", "content": "好的，我会记住。"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "chat.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "fast"},
        }


def test_reply_service_persists_completed_turn_through_memory_writer() -> None:
    store = _Store()
    writer = _Writer()
    service = ReplyServiceV2(
        orchestrator=_Orchestrator(),
        conversation_store=store,
        memory_writer=writer,
    )
    payload = SimpleNamespace(
        question="我更喜欢简短回答",
        actor_role="student",
        conversation_id="conv-1",
        owner="student-1",
        course_id="course-a",
        model_id=None,
        selected_doc_ids=[],
        allow_rag=False,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    result = service.reply(payload)

    assert store.writes
    assert writer.calls[0]["user_message"] == "我更喜欢简短回答"
    assert writer.calls[0]["assistant_message"] == "好的，我会记住。"
    assert result["trace"]["agent_memory_write"]["written_count"] == 1
