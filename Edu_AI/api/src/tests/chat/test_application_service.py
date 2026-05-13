from app.chat.application.chat_app_service import ChatAppService
from app.chat.domain.contracts import ChatRequestV2


class DummyOrchestrator:
    def dispatch(self, request):
        return {
            "message": {"role": "assistant", "content": f"echo:{request.question}"},
            "conversation": {"conversation_id": request.conversation_id or "conv-1"},
            "action": {"name": "chat.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "fast"},
        }


def test_chat_app_service_normalizes_then_dispatches():
    payload = type(
        "Payload",
        (),
        {
            "question": "你好",
            "conversation_id": "conv-1",
            "owner": "teacher-a",
            "model_id": None,
            "course_id": None,
            "artifact_id": None,
            "allow_rag": False,
            "allow_web": False,
            "use_rag": False,
            "selected_doc_ids": [],
            "action_hint": None,
        },
    )()

    service = ChatAppService(
        normalizer=lambda raw: ChatRequestV2(question=raw.question, conversation_id=raw.conversation_id),
        orchestrator=DummyOrchestrator(),
        response_builder=type("Builder", (), {"build_http_response": staticmethod(lambda result: result)})(),
    )

    result = service.chat(payload)

    assert result["message"]["content"] == "echo:你好"
    assert result["conversation"]["conversation_id"] == "conv-1"

