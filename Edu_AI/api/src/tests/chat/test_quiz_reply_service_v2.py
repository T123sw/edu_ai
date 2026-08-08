from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2, build_default_reply_service_v2


class DummyOrchestrator:
    def __init__(self, result):
        self.result = result

    def dispatch(self, request):
        return self.result


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["action"]["name"]))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "chat", "status_label": "生成练习", "source_labels": ["当前会话"]}


class DummyCourseStorageManager:
    def __init__(self):
        self.saved = []

    def save_generated_material(
        self, *, course_id, material_type, material_id, material_data,
        file_data=None, **_metadata,
    ):
        self.saved.append(
            {
                "course_id": course_id,
                "material_type": material_type,
                "material_id": material_id,
                "material_data": material_data,
            }
        )
        return True


def test_reply_service_persists_completed_quiz_artifact():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {"conversation_id": "conv-quiz-reply-1"},
            "action": {"name": "generate.quiz"},
            "workflow": {"type": "quiz", "status": "completed"},
            "artifacts": [
                {
                    "artifact_id": "quiz-1",
                    "artifact_type": "quiz",
                    "title": "fractions-quiz.json",
                    "content": {
                        "title": "fractions quiz",
                        "difficulty": "medium",
                        "question_type": "choice",
                        "questions": [{"id": "1", "type": "choice", "stem": "q", "answer": "A", "explanation": "e"}],
                    },
                    "generation_state": {"status": "completed"},
                }
            ],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "quiz"},
        }
    )
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    course_storage = DummyCourseStorageManager()
    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=store,
        context_builder=SimpleNamespace(build=lambda request: snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=course_storage,
    )
    payload = SimpleNamespace(
        question="generate a quiz",
        conversation_id="conv-quiz-reply-1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.quiz",
        owner="u1",
    )

    result = service.reply(payload)

    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert course_storage.saved[0]["course_id"] == "course-1"
    assert course_storage.saved[0]["material_type"] == "quiz"
    assert course_storage.saved[0]["material_data"]["title"] == "fractions-quiz.json"


def test_build_default_reply_service_v2_registers_quiz_workflow(monkeypatch):
    seen = {}
    llm_marker = object()

    class DummyStoreImpl:
        def ensure_conversation(self, conversation_id, question, owner=None):
            return None

        def get_messages(self, conversation_id, limit=20):
            return []

        def get_state(self, conversation_id):
            return {}

        def append_message(self, conversation_id, role, content, sources=None):
            return None

        def update_state(self, conversation_id, patch):
            return None

    class DummyGateway:
        def chat(self, messages):
            return "ok"

    class DummyQuizRuntime:
        def __init__(self, **kwargs):
            seen["runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "quiz"},
                "conversation": {"conversation_id": request.conversation_id or "conv-quiz-1"},
                "action": {"name": "generate.quiz"},
                "workflow": {"type": "quiz", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "quiz"},
            }

    class DummyMainOrchestrator:
        def __init__(self, *, workflow_registry, **kwargs):
            seen["workflow_registry"] = workflow_registry

        def dispatch(self, request):
            runtime = seen["workflow_registry"]["quiz"]
            return runtime.run(
                request=request,
                snapshot=None,
                decision=SimpleNamespace(path="workflow", action="generate.quiz", workflow_name="quiz"),
            )

    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.ConversationStoreAdapter",
        lambda: SimpleNamespace(
            storage=DummyStoreImpl(),
            load_snapshot=lambda conversation_id: {"messages": [], "state": {}},
            write_v2_result=lambda conversation_id, request, result: None,
        ),
    )
    monkeypatch.setattr(
        "app.chat.application.reply_service_v2.build_default_gateway",
        lambda model_id=None: DummyGateway(),
    )
    monkeypatch.setattr("app.chat.application.reply_service_v2.MainOrchestrator", DummyMainOrchestrator)
    monkeypatch.setattr("app.chat.application.reply_service_v2.QuizWorkflowRuntime", DummyQuizRuntime, raising=False)
    monkeypatch.setattr("app.chat.application.reply_service_v2.get_fallback_llm", lambda: llm_marker)

    service = build_default_reply_service_v2()
    payload = SimpleNamespace(
        question="generate a quiz",
        conversation_id="conv-quiz-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint="generate.quiz",
        owner="u1",
    )

    result = service.reply(payload)

    assert result["workflow"]["type"] == "quiz"
    assert "quiz" in seen["workflow_registry"]
    assert seen["runtime_kwargs"]["generation_context_builder"] is not None
    assert seen["runtime_kwargs"]["quiz_assembler"] is not None
    assert seen["runtime_kwargs"]["quiz_context_organizer"] is not None
    assert getattr(seen["runtime_kwargs"]["quiz_context_organizer"], "llm", None) is llm_marker
    assert seen["runtime_kwargs"]["quiz_readiness_judge"] is not None
    assert getattr(seen["runtime_kwargs"]["quiz_readiness_judge"], "llm", None) is llm_marker
    assert seen["runtime_kwargs"]["quiz_generator"] is not None
