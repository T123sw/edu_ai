from pathlib import Path
import uuid

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from core.conversation_storage import ConversationStorage


def test_conversation_store_adapter_persists_rich_evidence_metadata():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    storage.ensure_conversation("conv-evidence-meta", "hello")
    adapter = ConversationStoreAdapter(storage=storage)

    class Capability:
        allow_rag = False
        allow_web = False
        selected_doc_ids = []

    class Request:
        question = "请分析这节课的课堂观察证据"
        capability = Capability()
        course_id = None
        owner = "teacher-a"

    adapter.write_v2_result(
        "conv-evidence-meta",
        Request(),
        {
            "message": {
                "role": "assistant",
                "content": "课堂前10分钟举手响应较少，后排学生多次走神，说明注意力维持不足。"
            },
            "conversation": {"conversation_id": "conv-evidence-meta"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        },
    )

    state = storage.get_state("conv-evidence-meta")
    evidence = state["conversation_memory"]["evidence_points"][0]
    messages = storage.get_messages("conv-evidence-meta")
    assistant_message_id = messages[-1]["message_id"]

    assert evidence["source_type"] == "assistant_message"
    assert evidence["source_message_ids"] == [assistant_message_id]
    assert evidence["confidence"] == "low"


def test_report_context_pipeline_preserves_rich_evidence_metadata():
    evidence = {
        "type": "observation",
        "content": "课堂前10分钟举手响应较少",
        "source_type": "assistant_message",
        "source_message_ids": ["conv-1:msg:a1", "conv-1:msg:a2"],
        "confidence": "medium",
    }
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        recent_messages=[{"message_id": "conv-1:msg:a2", "role": "assistant", "content": "课堂前10分钟举手响应较少。"}],
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "evidence_points": [evidence],
        },
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-1",
        owner="teacher-a",
        capability={
            "allow_rag": False,
            "allow_web": False,
            "allow_tools": True,
            "selected_doc_ids": [],
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

    assert context.evidence_points == [evidence]
    assert gathered["evidence_points"] == [evidence]
    assert seen["gathered_context"]["evidence_points"] == [evidence]
