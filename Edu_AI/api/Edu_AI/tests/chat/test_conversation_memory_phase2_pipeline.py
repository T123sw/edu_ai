from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.application.route_chat_service import RouteChatService
from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from core.conversation_storage import ConversationStorage


class DummyGateway:
    def chat(self, messages, temperature=0.2, max_tokens=1200):
        return "课堂前10分钟举手响应较少，后排学生多次走神，互动推进不足。"


class DummyLegacyService:
    def chat(self, **kwargs):
        return {
            "answer": "旧回复",
            "conversation_id": kwargs.get("conversation_id") or "legacy-conv",
            "model_id": "",
            "intent_category": "chat",
            "meta": {},
        }

    def chat_stream_with_meta(self, **kwargs):
        return {"conversation_id": "legacy-conv"}, []

    @staticmethod
    def skill_health_check(meta):
        return {"score": 100.0, "grade": "A", "summary": "ok", "details": {}}


def test_conversation_store_adapter_persists_phase2_memory_fields():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-phase2", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Capability:
        allow_rag = False
        allow_web = False
        selected_doc_ids = []

    class Request:
        question = "请分析高一物理课堂前10分钟参与度低、后排学生容易分心的问题，并按提纲形式输出"
        capability = Capability()
        course_id = "course-1"
        owner = "teacher-a"

    adapter.write_v2_result(
        "conv-phase2",
        Request(),
        {
            "message": {
                "role": "assistant",
                "content": "课堂前10分钟举手响应较少，后排学生多次走神，互动没有形成持续推进。"
            },
            "conversation": {"conversation_id": "conv-phase2"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    state = storage.get_state("conv-phase2")
    memory = state["conversation_memory"]

    assert any("前10分钟" in item for item in memory["student_signals"])
    assert any("走神" in item["content"] for item in memory["evidence_points"])
    assert "提纲形式输出" in memory["constraints"]["extra_constraints"]


def test_route_chat_service_persists_phase2_memory_fields_on_new_path():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)

    service = RouteChatService(
        legacy_service=DummyLegacyService(),
        gateway_factory=lambda model_id: DummyGateway(),
        enable_new_chat=True,
        conversation_store=adapter,
    )

    service.chat(
        question="请分析高一物理课堂前10分钟参与度低、后排学生容易分心的问题，并按提纲形式输出",
        conversation_id="conv-phase2-route",
        model_id=None,
        use_rag=False,
        selected_doc_ids=[],
        owner="teacher-a",
        course_id="course-1",
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    )

    state = storage.get_state("conv-phase2-route")
    memory = state["conversation_memory"]

    assert any("前10分钟" in item for item in memory["student_signals"])
    assert memory["evidence_points"]
    assert "提纲形式输出" in memory["constraints"]["extra_constraints"]


def test_report_context_pipeline_carries_phase2_memory_fields():
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        recent_messages=[{"role": "assistant", "content": "课堂前10分钟举手响应较少，后排学生多次走神。"}],
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["课堂前10分钟举手响应较少"],
            "constraints": {"audience": "教研组", "extra_constraints": ["提纲形式输出"]},
            "teaching_issues": ["互动推进不足"],
            "student_signals": ["后排学生多次走神"],
            "evidence_points": [{"type": "observation", "content": "课堂前10分钟举手响应较少"}],
        },
        active_context={
            "current_course_id": "course-1",
            "active_artifact_id": "artifact-2",
            "active_artifact_type": "report_outline",
            "pinned_doc_ids": ["doc-1"],
        },
        referenced_artifact_ids=["artifact-1"],
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-1",
        owner="teacher-a",
        capability={
            "allow_rag": True,
            "allow_web": False,
            "allow_tools": True,
            "selected_doc_ids": ["doc-fallback"],
        },
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )
    gathered = ReportAssembler().from_generation_context(context)

    seen = {}

    class InspectingEngine:
        def invoke(self, state):
            seen.update(state)
            return {"reply": "ok", "status": "running"}

    runtime = ReportWorkflowRuntime(engine=InspectingEngine())
    runtime.run(request=request, snapshot=snapshot, decision=None)

    assert context.student_signals == ["后排学生多次走神"]
    assert context.evidence_points == [{"type": "observation", "content": "课堂前10分钟举手响应较少"}]
    assert gathered["student_signals"] == ["后排学生多次走神"]
    assert gathered["evidence_points"] == [{"type": "observation", "content": "课堂前10分钟举手响应较少"}]
    assert seen["gathered_context"]["student_signals"] == ["后排学生多次走神"]
    assert seen["gathered_context"]["evidence_points"] == [{"type": "observation", "content": "课堂前10分钟举手响应较少"}]
