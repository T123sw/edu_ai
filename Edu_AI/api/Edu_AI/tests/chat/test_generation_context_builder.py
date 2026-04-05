from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder


def test_generation_context_builder_builds_report_context_from_snapshot():
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        recent_messages=[
            {"role": "user", "content": "课堂前10分钟学生容易分心"},
            {"role": "assistant", "content": "我先整理课堂问题"},
        ],
        summary="课堂问题集中在参与度和开场控制",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["前10分钟学生分心明显"],
            "constraints": {"audience": "教研组", "style_notes": []},
            "teaching_issues": ["开场吸引力不足"],
            "student_signals": ["前10分钟注意力分散"],
            "evidence_points": [{"type": "observation", "content": "前10分钟学生分心明显"}],
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

    assert context.resource_type == "report"
    assert context.summary_text == "课堂问题集中在参与度和开场控制"
    assert context.confirmed_facts == ["前10分钟学生分心明显"]
    assert context.selected_doc_ids == ["doc-1"]
    assert context.current_course_id == "course-1"
    assert context.referenced_artifact_ids == ["artifact-1"]
    assert context.recent_relevant_messages[-1]["content"] == "我先整理课堂问题"
def test_generation_context_builder_prefers_user_stated_facts_over_legacy_bucket():
    snapshot = ConversationSnapshot(
        conversation_id="conv-2",
        recent_messages=[],
        summary="课堂分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "user_stated_facts": ["前10分钟学生多次走神"],
            "assistant_fact_candidates": ["开场吸引力不足"],
            "confirmed_facts": ["旧兼容事实"],
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
        conversation_id="conv-2",
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

    assert context.confirmed_facts == ["前10分钟学生多次走神"]


def test_generation_context_builder_keeps_goal_and_constraint_compat_projection():
    snapshot = ConversationSnapshot(
        conversation_id="conv-3",
        recent_messages=[],
        summary="报告准备",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "explicit_user_goals": ["分析问题"],
            "derived_workflow_goal": "生成报告",
            "user_goals": ["生成报告", "分析问题"],
            "explicit_user_constraints": {"audience": "教研组", "tone": "正式", "extra_constraints": ["提纲形式输出"]},
            "derived_workflow_constraints": {"course_id": "course-1"},
            "constraints": {"audience": "教研组", "tone": "正式", "course_id": "course-1", "extra_constraints": ["提纲形式输出"]},
            "confirmed_facts": [],
            "teaching_issues": [],
            "student_signals": [],
            "evidence_points": [],
        },
        active_context={},
        referenced_artifact_ids=[],
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-3",
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

    assert context.user_goals == ["生成报告", "分析问题"]
    assert context.constraints["audience"] == "教研组"
    assert context.constraints["course_id"] == "course-1"


def test_generation_context_builder_never_backfills_confirmed_facts_from_summary():
    snapshot = ConversationSnapshot(
        conversation_id="conv-4",
        recent_messages=[],
        summary="前10分钟学生多次走神，后排回应也比较少",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["分析问题"],
            "confirmed_facts": [],
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
        conversation_id="conv-4",
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

    assert context.summary_text == "前10分钟学生多次走神，后排回应也比较少"
    assert context.confirmed_facts == []
