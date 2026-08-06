"""Agent tool handler: enqueue a durable report-generation command."""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from uuid import uuid4


def handle_generate_report(name: str, args: dict, ctx) -> dict:
    subject = str(args.get("subject", "")).strip()
    confirmed_outline = str(args.get("confirmed_outline", "")).strip()
    focus = str(args.get("focus", "")).strip()
    length_hint = str(args.get("length_hint", "")).strip()

    if not subject:
        return error_result(name, "missing_subject", "报告主题不能为空")

    allow_rag = bool(getattr(getattr(ctx, "capability", None), "allow_rag", False))
    selected_doc_ids = list(getattr(getattr(ctx, "capability", None), "selected_doc_ids", []) or [])
    owner = getattr(getattr(ctx, "request", None), "owner", None)
    course_id = getattr(getattr(ctx, "request", None), "course_id", None)

    # Phase 6-A: images accumulated by reflect_node from this turn's image_search calls.
    # tools_node sets ctx.accumulated_images before dispatch.
    accumulated_images = list(getattr(ctx, "accumulated_images", []) or [])

    # Phase 6-A.2: when VLM review is on, VisionReflector already downloaded +
    # reviewed these images, so they arrive already-localized (_localized=True,
    # url=/api/images/searched/...). Skip re-download in that case.
    try:
        command = GenerationCommand(
            resource_type="report",
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
                "focus": focus,
                "length_hint": length_hint,
                "allow_rag": allow_rag,
                "accumulated_images": accumulated_images,
            },
            idempotency_key=f"agent-report-{uuid4()}",
        )
        job = generation_command_service.submit(command)
        task_id = job.edu_job_id
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交报告生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "report"},
    )
