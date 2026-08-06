"""Agent tool handler: enqueue a durable lesson-plan command."""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from uuid import uuid4


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

    try:
        selected_doc_ids = list(
            getattr(
                getattr(ctx, "capability", None),
                "selected_doc_ids",
                [],
            )
            or []
        )
        command = GenerationCommand(
            resource_type="lesson_plan",
            owner_user_id=str(owner or ""),
            course_id=str(course_id or ""),
            scope_type=str(
                getattr(ctx.request, "scope_type", None) or "course"
            ),
            scope_id=getattr(ctx.request, "scope_id", None),
            selected_doc_ids=selected_doc_ids,
            config={
                "entrypoint": "agent",
                "title": subject,
                "subject": subject,
                "confirmed_outline": confirmed_outline,
                "grade": grade,
                "duration_minutes": duration_minutes,
                "conversation_id": conversation_id,
            },
            idempotency_key=f"agent-lesson-{uuid4()}",
        )
        job = generation_command_service.submit(command)
        task_id = job.edu_job_id
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交教案生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "lesson_plan"},
    )
