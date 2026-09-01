from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.orchestrator.status_card_label_mapper import StatusCardLabelMapper


def test_status_card_builder_builds_workflow_card_from_snapshot():
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        summary="围绕课堂观察整理报告。",
        conversation_memory={
            "current_topics": ["课堂纪律", "学生参与度"],
            "user_goals": ["分析课堂问题"],
            "confirmed_facts": ["课堂前半段学生回应较少"],
            "teaching_issues": ["导入吸引力不足", "互动设计偏少"],
            "constraints": {
                "audience": "教研组",
                "tone": "正式",
                "length": "800字",
                "grade_level": "高一",
                "subject": "物理",
            },
        },
        active_context={
            "current_course_id": "course-1",
            "pinned_doc_ids": ["doc-1", "doc-2"],
            "active_artifact_id": "artifact-1",
            "active_artifact_type": "report",
        },
        capability=CapabilityPolicy(allow_rag=True, allow_web=False, selected_doc_ids=["doc-1", "doc-2"]),
    )

    card = StatusCardBuilder(label_mapper=StatusCardLabelMapper()).build(
        snapshot=snapshot,
        workflow={"type": "report", "status": "running"},
        capability=snapshot.capability,
    )

    assert card.mode == "workflow"
    assert card.status_label == "正在生成报告"
    assert card.workflow_label == "报告"
    assert card.goal == "生成报告"
    assert card.topics == ["课堂纪律", "学生参与度"]
    assert card.issues == ["导入吸引力不足", "互动设计偏少"]
    assert card.confirmed_facts == ["课堂前半段学生回应较少"]
    assert "当前会话" in card.source_labels
    assert "已选文档 2 份" in card.source_labels
    assert "当前课程" in card.source_labels
    assert card.active_artifact_label == "当前产物：报告"
    assert card.waiting_label is None
    assert card.suggested_actions == ["继续生成"]
    assert card.audience == "教研组"
    assert card.allow_rag is True
    assert card.allow_web is False


def test_status_card_builder_falls_back_for_low_state_chat():
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        summary="",
        conversation_memory={},
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(
        snapshot=snapshot,
        workflow=None,
        capability=snapshot.capability,
    )

    assert card.mode == "chat"
    assert card.status_label == "普通对话"
    assert card.topics == []
    assert card.goal is None
    assert card.issues == []
    assert card.source_labels == ["当前会话"]
    assert card.waiting_label == "继续提问，或告诉我你想生成什么"
    assert card.suggested_actions == ["继续提问", "生成报告"]


def test_status_card_label_mapper_supports_awaiting_confirm_copy():
    mapper = StatusCardLabelMapper()

    assert mapper.map_status(workflow_type="report", status="awaiting_confirm", phase="confirming", required_slots=[]) == "等待你确认报告大纲"
    assert mapper.map_waiting_label(workflow_type="report", status="awaiting_confirm", phase="confirming", required_slots=[]) == "等待你确认报告大纲"
    assert mapper.map_suggested_actions(workflow_type="report", status="awaiting_confirm", required_slots=[]) == ["确认并继续", "调整要求"]


def test_status_card_builder_prefers_explicit_user_goal_for_chat_goal_text():
    snapshot = ConversationSnapshot(
        conversation_id="conv-2",
        summary="",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "explicit_user_goals": ["分析问题"],
            "derived_workflow_goal": "生成报告",
            "user_goals": ["生成报告", "分析问题"],
            "constraints": {},
        },
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(
        snapshot=snapshot,
        workflow=None,
        capability=snapshot.capability,
    )

    assert card.mode == "chat"
    assert card.goal == "分析问题"


def test_status_card_builder_prefers_user_stated_facts_over_legacy_confirmed_bucket():
    snapshot = ConversationSnapshot(
        conversation_id="conv-3",
        summary="前10分钟学生多次走神，后排回应也比较少",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_stated_facts": ["前10分钟学生多次走神"],
            "confirmed_facts": ["旧兼容事实"],
            "constraints": {},
        },
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(
        snapshot=snapshot,
        workflow=None,
        capability=snapshot.capability,
    )

    assert card.confirmed_facts == ["前10分钟学生多次走神"]
