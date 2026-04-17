from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.workflow_state import WorkflowState
from app.chat.orchestrator.route_rules import decide_route


def test_lesson_plan_keyword_without_action_hint_uses_workflow_path():
    request = ChatRequestV2(question="根据以上内容，总结为教案")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "lesson_plan"
    assert decision.reason == "explicit_lesson_plan"


def test_plain_chat_uses_fast_path():
    request = ChatRequestV2(question="帮我解释牛顿第二定律")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "fast"
    assert decision.action == "chat.reply"


def test_report_command_uses_workflow_path():
    request = ChatRequestV2(question="根据以上内容生成报告", action_hint="generate.report")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "report"


def test_report_keyword_without_action_hint_uses_workflow_path():
    request = ChatRequestV2(question="帮我整理成报告")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "report"


def test_active_artifact_rewrite_stays_in_fast_path():
    snapshot = SimpleNamespace(active_artifact={"artifact_id": "a1", "artifact_type": "report"})
    request = ChatRequestV2(question="再正式一点")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "fast"
    assert decision.action == "chat.rewrite"


def test_research_action_prefers_workflow_path():
    request = ChatRequestV2(question="帮我查一下最新课程标准", action_hint="research.lookup")

    decision = decide_route(request=request, snapshot=None, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "research"


def test_existing_workflow_resumes_when_no_interrupt_signal():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="running",
        stage="collecting",
    )
    request = ChatRequestV2(question="继续")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "workflow"
    assert decision.workflow_name == "report"
    assert decision.reason == "resume_workflow"


def test_existing_running_workflow_can_switch_back_to_fast_chat():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="running",
        stage="collecting",
    )
    request = ChatRequestV2(question="回到普通对话")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "fast"
    assert decision.action == "chat.reply"
    assert decision.reason == "explicit_chat_exit"


def test_existing_completed_workflow_can_switch_back_to_fast_chat():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="completed",
        stage="completed",
    )
    request = ChatRequestV2(question="回到普通对话")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "fast"
    assert decision.action == "chat.reply"
    assert decision.reason == "explicit_chat_exit"


def test_existing_running_workflow_can_switch_to_ppt():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="running",
        stage="collecting",
    )
    request = ChatRequestV2(question="基于以上内容，生成PPT")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "workflow"
    assert decision.action == "generate.ppt"
    assert decision.workflow_name == "ppt"
    assert decision.reason == "explicit_ppt"


def test_existing_completed_workflow_can_switch_to_ppt():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="completed",
        stage="completed",
    )
    request = ChatRequestV2(question="基于以上内容，生成PPT")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "workflow"
    assert decision.action == "generate.ppt"
    assert decision.workflow_name == "ppt"
    assert decision.reason == "explicit_ppt"


def test_interrupt_signal_breaks_existing_workflow_and_starts_new_action():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="running",
        stage="collecting",
    )
    request = ChatRequestV2(question="算了，先帮我出一份教案", action_hint="generate.lesson_plan")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "workflow"
    assert decision.action == "generate.lesson_plan"
    assert decision.workflow_name == "lesson_plan"
    assert decision.reason == "explicit_lesson_plan"


def test_interrupt_signal_without_new_action_falls_back_to_chat():
    workflow_state = WorkflowState(
        workflow_id="wf-1",
        workflow_type="report",
        status="running",
        stage="collecting",
    )
    request = ChatRequestV2(question="重新开始")

    decision = decide_route(request=request, snapshot=None, workflow_state=workflow_state)

    assert decision.path == "fast"
    assert decision.action == "chat.reply"
    assert decision.reason == "interrupt_to_chat"


def test_report_followup_from_active_context_uses_workflow_without_explicit_keyword():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "report",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "report_outline",
        },
        conversation_memory={
            "user_goals": ["生成报告"],
            "derived_workflow_goal": "生成报告",
        },
    )
    request = ChatRequestV2(question="确认并继续")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "report"
    assert decision.reason == "resume_active_report_context"


def test_report_followup_with_outline_phrase_uses_workflow_from_context():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "report",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "report_outline",
        },
        conversation_memory={
            "user_goals": ["生成报告"],
        },
    )
    request = ChatRequestV2(question="按这个大纲开始写")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "report"


def test_lesson_plan_followup_from_active_context_uses_workflow_without_explicit_keyword():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "lesson_plan",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "lesson_plan_outline",
        },
        conversation_memory={
            "user_goals": ["教案"],
            "derived_workflow_goal": "教案",
        },
    )
    request = ChatRequestV2(question="继续")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "lesson_plan"
    assert decision.reason == "resume_active_lesson_plan_context"


def test_lesson_plan_followup_from_memory_and_outline_artifact_uses_workflow():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={
            "active_workflow_type": "",
            "active_workflow_status": "",
            "active_artifact_type": "lesson_plan_outline",
        },
        conversation_memory={
            "user_goals": ["整理教案"],
            "derived_workflow_goal": "教案",
        },
    )
    request = ChatRequestV2(question="确认并继续")

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "lesson_plan"
