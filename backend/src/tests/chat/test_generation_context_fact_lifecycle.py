from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder


def test_generation_context_builder_ignores_retracted_user_claims():
    snapshot = ConversationSnapshot(
        conversation_id="conv-fact-lifecycle",
        recent_messages=[],
        summary="",
        conversation_memory={
            "user_claims": [
                {"content": "前10分钟学生多次走神", "status": "retracted"},
                {"content": "后10分钟学生多次走神", "status": "stated"},
            ],
            "confirmed_facts": ["前10分钟学生多次走神", "后10分钟学生多次走神"],
            "constraints": {},
            "teaching_issues": [],
            "student_signals": [],
            "evidence_points": [],
        },
        active_context={},
        referenced_artifact_ids=[],
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-fact-lifecycle",
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

    assert context.confirmed_facts == ["后10分钟学生多次走神"]
