"""Agent tool handler: generate_lesson_plan.

Calls LessonPlanGenerationEngine._generate_content() directly via submit_callable_task.
State dict is constructed from agent tool args — skips asking/outlining phases.
"""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result


def handle_generate_lesson_plan(name: str, args: dict, ctx) -> dict:
    subject = str(args.get("subject", "")).strip()
    confirmed_outline = str(args.get("confirmed_outline", "")).strip()
    grade = str(args.get("grade", "")).strip()
    duration_minutes = int(args.get("duration_minutes") or 45)

    if not subject:
        return error_result(name, "missing_subject", "课题不能为空")

    conversation_id = str(getattr(ctx.request, "conversation_id", "") or "lesson-plan")
    owner = getattr(ctx.request, "owner", None)
    course_id = getattr(ctx.request, "course_id", None)

    def _run():
        from app.chat.application.lesson_plan_service_v2 import LessonPlanGenerationEngine
        from app.chat.agents.report_generation import get_fallback_llm

        engine = LessonPlanGenerationEngine(llm=get_fallback_llm())
        state = {
            "lesson_plan_slots": {
                "topic": subject,
                "audience": grade,
                "duration": f"{duration_minutes}分钟",
                "lesson_type": "知识讲解",
            },
            "lesson_plan_preparation_result": {},
            # Pass confirmed_outline as the outline dict so _build_content_prompt
            # includes it verbatim when serialising to the LLM prompt.
            "lesson_plan_outline": {
                "topic": subject,
                "outline_markdown": confirmed_outline,
            },
            "conversation_id": conversation_id,
        }
        result = engine._generate_content(state=state)
        return {
            "status": result.get("status", "completed"),
            "artifacts": result.get("artifacts", []),
        }

    try:
        from app.chat.tasks.background_runner import submit_callable_task
        task_id = submit_callable_task(
            fn=_run,
            workflow_type="lesson_plan",
            owner_user_id=owner,
            course_id=course_id,
            scope_type=str(getattr(ctx.request, "scope_type", None) or "course"),
            scope_id=getattr(ctx.request, "scope_id", None),
            input_summary={"title": subject},
        )
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交教案生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "lesson_plan"},
    )
