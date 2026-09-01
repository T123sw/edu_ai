"""Compile a validated task contract into the small fixed workflow vocabulary."""
from __future__ import annotations

from app.chat.domain.teaching_task_contract import TeachingTaskContract
from app.chat.runtime.planning.schema import Plan, PlanStep
from app.chat.runtime.research.planner import build_research_plan


_CONFIRMABLE = {"report", "lesson_plan", "classroom"}


def compile_plan(contract: TeachingTaskContract, state: dict | None = None) -> Plan:
    state = state or {}
    active_outline = dict(state.get("active_draft_outline") or {})
    steps: list[PlanStep] = []
    template_id = "qa"

    def add(
        action: str,
        title: str,
        expected: list[str] | None = None,
        *,
        required: bool = True,
        constraints: dict | None = None,
    ):
        index = len(steps) + 1
        steps.append(PlanStep(
            index=index,
            user_title=title,
            internal_action=action,
            expected_tools=list(expected or []),
            constraints=dict(constraints or {}),
            tool_allowlist=list(expected or []),
            depends_on=[str(index - 1)] if index > 1 else [],
            required=required,
            success_predicate=_success_predicate(action),
            failure_policy=_failure_policy(action),
            max_attempts=2 if action.startswith("retrieve") else 1,
        ))

    retrieval_tools = []
    if contract.requires_rag:
        retrieval_tools.append("rag_search")
    if contract.requires_web:
        retrieval_tools.append("web_search")
    if retrieval_tools and not contract.clarification.required:
        research_plan = build_research_plan(contract)
        add(
            "retrieve_context",
            "检索已启用的资料来源",
            retrieval_tools,
            constraints={
                "require_sources": True,
                "min_sources": 1,
                "research_plan": research_plan.model_dump(mode="json"),
            },
        )

    if contract.clarification.required:
        add("clarify", "确认关键信息", [])
        template_id = "clarification"
    elif contract.intent == "qa":
        add("answer_question", "整理教学要点", [])
        add("verify", "核对来源与回答", ["verify_task"])
        add("report_result", "汇报结果", [])
        template_id = "qa"
    elif contract.intent == "status":
        if contract.task_domain == "course_learning":
            tool = (
                "get_my_learning_progress"
                if contract.actor_role == "student"
                else "get_course_learning_progress"
            )
            add("learning_status", "查询课程学习进度", [tool])
            add("report_result", "汇报学习结果", [])
            template_id = "course_learning_status"
        elif contract.task_domain == "generation_job":
            add("generation_status", "查询后台生成状态", ["query_generation_job_status"])
            add("report_result", "汇报生成结果", [])
            template_id = "generation_job_status"
        else:
            add("clarify", "确认要查询学习任务还是生成任务", [])
            template_id = "task_domain_clarification"
    elif contract.intent == "cancel":
        if contract.task_domain == "generation_job":
            add("cancel", "取消目标生成任务", ["cancel_task"])
            add("report_result", "汇报结果", [])
            template_id = "generation_job_cancel"
        else:
            add("clarify", "课程学习任务暂不支持取消；请确认是否要取消生成任务", [])
            template_id = "task_domain_clarification"
    elif contract.intent == "modify":
        # A modification is never an invisible overwrite.  It creates a new
        # outline revision and returns to the same explicit confirmation gate.
        resource_type = str(active_outline.get("resource_type") or (contract.resource_types or ["report"])[0])
        add("draft_outline", f"按新要求修订{resource_type}大纲", ["draft_outline"])
        add("confirm_outline", "展示修订稿并等待确认", [])
        template_id = "modify_outline"
    elif contract.intent == "confirm":
        resource_types = contract.resource_types or [str(active_outline.get("resource_type") or "report")]
        if contract.requires_images:
            add("fetch_visuals", f"为{contract.topic}搜集配图", ["image_search"])
        _append_generation_steps(add, contract, resource_types, active_outline)
        add("verify", "核对任务与材料", ["verify_task"])
        add("report_result", "汇报结果", [])
        template_id = "confirmed_generation"
    elif contract.intent == "prepare_bundle":
        if active_outline:
            if contract.requires_images:
                add("fetch_visuals", f"为{contract.topic}搜集配图", ["image_search"])
            _append_generation_steps(add, contract, contract.resource_types, active_outline)
            add("verify", "核对材料包", ["verify_task"])
            add("report_result", "汇报结果", [])
            template_id = "default_bundle_confirmed"
        else:
            add("draft_outline", f"起草{contract.topic}教学材料包结构", ["draft_outline"])
            add("confirm_outline", "展示材料包结构并等待确认", [])
            template_id = "default_bundle"
    else:  # generate_single
        resource_types = contract.resource_types
        if any(resource in _CONFIRMABLE for resource in resource_types) and not active_outline:
            add("draft_outline", f"起草{contract.topic}资源结构", ["draft_outline"])
            add("confirm_outline", "展示结构并等待确认", [])
            template_id = "single_confirmable"
        else:
            if contract.requires_images:
                add("fetch_visuals", f"为{contract.topic}搜集配图", ["image_search"])
            _append_generation_steps(add, contract, resource_types, active_outline)
            add("verify", "核对任务与材料", ["verify_task"])
            add("report_result", "汇报结果", [])
            template_id = "single_generation"

    return Plan(
        steps=steps,
        resource_type=(
            contract.resource_types[0]
            if len(contract.resource_types) == 1
            else "bundle" if len(contract.resource_types) > 1 else "unknown"
        ),
        subject=contract.topic,
        template_id=template_id,
        contract=contract.model_dump(mode="json"),
        global_constraints={
            "max_retries_per_step": 1,
            "max_total_reflect_retries": 2,
            "max_replans": 1,
        },
        can_replan=True,
    )


def _append_generation_steps(add, contract: TeachingTaskContract, resources: list[str], active_outline: dict) -> None:
    for resource in resources:
        label = {
            "report": "报告", "lesson_plan": "教案", "quiz": "练习题", "blog": "教学博客",
            "flashcard": "闪卡", "graph": "思维导图", "game": "课堂小游戏", "classroom": "AI 课堂",
        }.get(resource, "资源")
        add("generate_resource", f"生成{contract.topic}{label}", [f"generate_{resource}"])


def _success_predicate(action: str) -> str:
    return {
        "retrieve_context": "all_required_evidence_present",
        "fetch_visuals": "visuals_present_or_explicit_degradation",
        "draft_outline": "outline_present",
        "confirm_outline": "awaiting_user",
        "generate_resource": "job_accepted_once",
        "verify": "verification_report_present",
        "report_result": "result_emitted",
        "clarify": "clarification_emitted",
    }.get(action, "completed")


def _failure_policy(action: str) -> str:
    if action in {"retrieve_context", "fetch_visuals"}:
        return "retry"
    if action == "generate_resource":
        return "stop"
    return "partial"
