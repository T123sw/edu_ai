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
    source_mode = (
        "selected_documents"
        if selected_doc_ids
        else ("course_auto" if allow_rag else "none")
    )
    owner = getattr(getattr(ctx, "request", None), "owner", None)
    course_id = getattr(getattr(ctx, "request", None), "course_id", None)

    # Phase 6-A: images accumulated by reflect_node from this turn's image_search calls.
    # tools_node sets ctx.accumulated_images before dispatch.
    accumulated_images = list(getattr(ctx, "accumulated_images", []) or [])
    if not accumulated_images:
        # LangGraph checkpoints may not expose a reflect-node list to a later
        # tool batch in the same turn. The execution context still owns the
        # successful image-search result, so recover it deterministically
        # instead of silently dropping the user's selected visual evidence.
        for cache_key, cached in dict(
            getattr(ctx, "_call_cache", {}) or {}
        ).items():
            if not str(cache_key).startswith("image_search:"):
                continue
            if not isinstance(cached, dict) or not cached.get("ok"):
                continue
            accumulated_images.extend(
                list((cached.get("payload") or {}).get("images") or [])
            )

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
            source_mode=source_mode,
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
