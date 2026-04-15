from app.chat.application.route_chat_service import RouteChatService
from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.workflows.lesson_plan.runtime import LessonPlanWorkflowRuntime


class DummyGateway:
    def chat(self, messages, temperature=0.2, max_tokens=1200):
        return "lesson plan"


class DummyLegacyService:
    @staticmethod
    def skill_health_check(meta):
        return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}


class _StubPreparation:
    def model_dump(self, exclude_none=True):
        return {
            "lesson_plan_intent": "generate_lesson_plan",
            "topic": "Fractions",
            "audience": "Grade 5",
            "objective": None,
            "duration": None,
            "lesson_type": None,
            "lesson_plan_context_summary": None,
            "constraints": {},
            "source_scope": [],
            "knowledge_points": [],
            "key_points": [],
            "hard_points": [],
            "teaching_methods": [],
            "class_profile": [],
            "resource_constraints": [],
            "style_constraints": [],
            "missing_critical_fields": ["objective_or_outline_basis"],
            "confidence": "low",
            "soft_confirm_message": "",
        }


def test_lesson_plan_runtime_invokes_engine_with_prepared_state_and_wraps_outline_artifact():
    called = {"state": None}

    class DummyEngine:
        def invoke(self, state):
            called["state"] = state
            return {
                "reply": "Fractions lesson plan draft",
                "status": "awaiting_human",
                "phase": "outlining",
                "lesson_plan_outline": [
                    {"title": "Warm-up", "sections": []},
                ],
                "sources": [{"source_id": "doc-1"}],
            }

    runtime = LessonPlanWorkflowRuntime(engine=DummyEngine())
    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-1",
        summary="Fractions lesson planning context",
        recent_messages=[{"role": "user", "content": "Help me plan a fractions lesson"}],
        conversation_memory={
            "current_topics": ["Fractions"],
            "user_goals": ["Create a lesson plan"],
            "confirmed_facts": ["Students can compare whole numbers"],
            "constraints": {
                "audience": "Grade 5",
                "duration": "45 minutes",
                "lesson_type": "new lesson",
                "objective": "Compare fractions",
            },
            "teaching_issues": ["Students confuse common denominators"],
            "student_signals": ["Needs visuals"],
            "evidence_points": [{"type": "note", "content": "exit ticket showed gaps"}],
        },
        active_context={},
    )

    result = runtime.run(
        request=ChatRequestV2(question="Help me plan a fractions lesson", conversation_id="conv-lesson-1"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["state"]["gathered_context"]["slot_hints"]["topic"] == "Fractions"
    assert called["state"]["lesson_plan_preparation_result"]["lesson_plan_intent"] == "generate_lesson_plan"
    assert called["state"]["readiness_decision"]["action"] == "strong_soft_confirm"
    assert called["state"]["generation_ready"] is True
    assert called["state"]["soft_confirmed"] is True
    assert result["message"]["content"] == "Fractions lesson plan draft"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"
    assert result["trace"]["workflow_name"] == "lesson_plan"


def test_lesson_plan_runtime_does_not_mark_objective_gap_as_generation_ready():
    called = {"state": None}

    class DummyEngine:
        def invoke(self, state):
            called["state"] = state
            return {
                "reply": "Need more detail",
                "status": "awaiting_human",
                "phase": "asking",
                "sources": [],
            }

    class StubOrganizer:
        def organize(self, *, context, request_question):
            return _StubPreparation()

    class StubJudge:
        def judge(self, result, *, entry_mode):
            return {
                "action": "ask_objective_or_outline_basis",
                "missing_critical_fields": ["objective_or_outline_basis"],
            }

    runtime = LessonPlanWorkflowRuntime(
        engine=DummyEngine(),
        lesson_plan_context_organizer=StubOrganizer(),
        lesson_plan_readiness_judge=StubJudge(),
    )
    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-gap",
        summary="",
        recent_messages=[{"role": "user", "content": "Help me plan a lesson"}],
        conversation_memory={},
        active_context={},
    )

    result = runtime.run(
        request=ChatRequestV2(question="Help me plan a lesson", conversation_id="conv-lesson-gap"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["state"]["readiness_decision"]["action"] == "ask_objective_or_outline_basis"
    assert called["state"].get("generation_ready") is None
    assert called["state"].get("soft_confirmed") is None
    assert result["workflow"]["status"] == "awaiting_confirm"


def test_lesson_plan_runtime_resumes_after_outline_confirmation():
    called = {"state": None}

    class DummyEngine:
        def invoke(self, state):
            called["state"] = state
            return {
                "final_response": "Lesson plan finalized",
                "status": "completed",
                "phase": "generating",
                "sources": [],
            }

    runtime = LessonPlanWorkflowRuntime(engine=DummyEngine())
    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-2",
        summary="Fractions lesson planning context",
        recent_messages=[{"role": "user", "content": "continue"}],
        conversation_memory={
            "current_topics": ["Fractions"],
            "user_goals": ["Create a lesson plan"],
            "confirmed_facts": ["Students can compare whole numbers"],
            "constraints": {
                "audience": "Grade 5",
                "duration": "45 minutes",
                "lesson_type": "new lesson",
                "objective": "Compare fractions",
            },
        },
        active_context={
            "active_workflow_type": "lesson_plan",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "lesson_plan_outline",
            "active_artifact_id": "lesson-plan-1:outline",
        },
        workflow_state={
            "workflow_id": "lesson-plan-1",
            "workflow_type": "lesson_plan",
            "status": "awaiting_confirm",
            "stage": "outlining",
            "artifacts": [
                {
                    "artifact_id": "lesson-plan-1:outline",
                    "artifact_type": "lesson_plan_outline",
                    "content": [{"title": "Warm-up", "sections": []}],
                }
            ],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="继续", conversation_id="conv-lesson-2"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["state"]["generation_ready"] is True
    assert called["state"]["soft_confirmed"] is True
    assert called["state"]["lesson_plan_outline"] == [{"title": "Warm-up", "sections": []}]
    assert result["message"]["content"] == "Lesson plan finalized"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"


def test_lesson_plan_runtime_preserves_dict_outline_content_when_resuming():
    called = {"state": None}

    class DummyEngine:
        def invoke(self, state):
            called["state"] = state
            return {
                "final_response": "Lesson plan finalized",
                "status": "completed",
                "phase": "generating",
                "sources": [],
            }

    runtime = LessonPlanWorkflowRuntime(engine=DummyEngine())
    outline_payload = {
        "title": "Warm-up",
        "sections": [{"title": "Starter", "items": []}],
    }
    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-3",
        summary="Fractions lesson planning context",
        recent_messages=[{"role": "user", "content": "继续"}],
        conversation_memory={
            "current_topics": ["Fractions"],
            "user_goals": ["Create a lesson plan"],
            "confirmed_facts": ["Students can compare whole numbers"],
            "constraints": {
                "audience": "Grade 5",
                "duration": "45 minutes",
                "lesson_type": "new lesson",
                "objective": "Compare fractions",
            },
        },
        active_context={
            "active_workflow_type": "lesson_plan",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "lesson_plan_outline",
            "active_artifact_id": "lesson-plan-3:outline",
        },
        workflow_state={
            "workflow_id": "lesson-plan-3",
            "workflow_type": "lesson_plan",
            "status": "awaiting_confirm",
            "stage": "outlining",
            "artifacts": [
                {
                    "artifact_id": "lesson-plan-3:outline",
                    "artifact_type": "lesson_plan_outline",
                    "content": outline_payload,
                }
            ],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="继续", conversation_id="conv-lesson-3"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["state"]["lesson_plan_outline"] == outline_payload
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"
    assert result["artifacts"][0]["content"] == outline_payload


def test_lesson_plan_runtime_passes_outline_feedback_to_engine_for_revision():
    called = {"state": None}

    class DummyEngine:
        def invoke(self, state):
            called["state"] = state
            return {
                "reply": "Updated outline",
                "status": "awaiting_human",
                "phase": "outlining",
                "lesson_plan_outline": {"basic_info": {"topic": "Fractions"}},
                "sources": [],
            }

    runtime = LessonPlanWorkflowRuntime(engine=DummyEngine())
    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-4",
        summary="Fractions lesson planning context",
        recent_messages=[{"role": "user", "content": "Add a group discussion section"}],
        conversation_memory={
            "current_topics": ["Fractions"],
            "user_goals": ["Create a lesson plan"],
            "confirmed_facts": ["Students can compare whole numbers"],
            "constraints": {
                "audience": "Grade 5",
                "duration": "45 minutes",
                "lesson_type": "new lesson",
                "objective": "Compare fractions",
            },
        },
        active_context={
            "active_workflow_type": "lesson_plan",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "lesson_plan_outline",
            "active_artifact_id": "lesson-plan-4:outline",
        },
        workflow_state={
            "workflow_id": "lesson-plan-4",
            "workflow_type": "lesson_plan",
            "status": "awaiting_confirm",
            "stage": "outlining",
            "artifacts": [
                {
                    "artifact_id": "lesson-plan-4:outline",
                    "artifact_type": "lesson_plan_outline",
                    "content": {"basic_info": {"topic": "Fractions"}},
                }
            ],
        },
    )

    result = runtime.run(
        request=ChatRequestV2(question="Add a group discussion section", conversation_id="conv-lesson-4"),
        snapshot=snapshot,
        decision=None,
    )

    assert called["state"]["lesson_plan_outline"] == {"basic_info": {"topic": "Fractions"}}
    assert called["state"]["human_feedback"] == "Add a group discussion section"
    assert called["state"]["generation_ready"] is True
    assert called["state"]["soft_confirmed"] is True
    assert result["message"]["content"] == "Updated outline"
    assert result["workflow"]["phase"] == "outlining"


def test_route_chat_service_registers_lesson_plan_workflow_runtime():
    seen = {}

    class DummyRuntime:
        def __init__(self, **kwargs):
            seen["runtime_kwargs"] = kwargs

        def run(self, *, request, snapshot, decision):
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": request.conversation_id or "conv-lesson-3"},
                "action": {"name": "generate.lesson_plan"},
                "workflow": {"type": "lesson_plan", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "lesson_plan"},
            }

    temp_service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
    )

    # Patch the runtime class after the service is created so the build path resolves it lazily.
    import app.chat.application.route_chat_service as route_chat_service_module

    original_runtime = route_chat_service_module.LessonPlanWorkflowRuntime
    route_chat_service_module.LessonPlanWorkflowRuntime = DummyRuntime
    try:
        data = temp_service.chat(
            question="帮我出一份教案",
            conversation_id="conv-lesson-3",
            model_id=None,
            use_rag=False,
            selected_doc_ids=[],
            owner="teacher-a",
            course_id=None,
            allow_web=False,
            action_hint="generate.lesson_plan",
            artifact_id=None,
        )
    finally:
        route_chat_service_module.LessonPlanWorkflowRuntime = original_runtime

    assert seen["runtime_kwargs"]["lesson_plan_context_organizer"] is not None
    assert seen["runtime_kwargs"]["lesson_plan_readiness_judge"] is not None
    assert data["answer"] == "ok"
