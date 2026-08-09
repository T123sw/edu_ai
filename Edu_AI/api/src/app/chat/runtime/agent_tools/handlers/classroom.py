"""Agent tool handler for the durable AI-classroom generation pipeline."""
from __future__ import annotations

import asyncio

from app.chat.runtime.agent_tools.handlers.report import _collect_research_evidence
from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.classroom_service import submit_classroom_generation_job
from core.course_storage import storage_manager


def handle_generate_classroom(name: str, args: dict, ctx) -> dict:
    topic = str(args.get("topic") or "").strip()
    if not topic:
        return error_result(name, "missing_topic", "AI 课堂主题不能为空")
    capability = getattr(ctx, "capability", None)
    allow_rag = bool(getattr(capability, "allow_rag", False))
    selected_doc_ids = list(getattr(capability, "selected_doc_ids", []) or [])
    source_mode = (
        "selected_documents"
        if selected_doc_ids
        else ("course_auto" if allow_rag else "none")
    )
    research_context, _ = _collect_research_evidence(ctx)
    request = getattr(ctx, "request", None)
    requirement = str(args.get("requirement") or "").strip() or (
        f"生成一份讲解{topic}的互动 AI 课堂"
    )
    try:
        job = asyncio.run(
            submit_classroom_generation_job(
                course_id=str(getattr(request, "course_id", None) or ""),
                requirement=requirement,
                owner=str(getattr(request, "owner", None) or ""),
                course_storage_manager=storage_manager,
                web_research_context=research_context or None,
                enable_web_search=False,
                enable_tts=bool(args.get("enable_tts", False)),
                source_mode=source_mode,
                selected_doc_ids=selected_doc_ids,
                topic=topic,
                audience=str(args.get("audience") or "学习者").strip(),
                scene_count=max(3, min(12, int(args.get("scene_count") or 6))),
                objectives=[
                    str(item).strip()
                    for item in list(args.get("objectives") or [])
                    if str(item).strip()
                ][:6],
                duration_minutes=max(
                    5, min(60, int(args.get("duration_minutes") or 25))
                ),
                teaching_style=str(args.get("teaching_style") or "guided"),
                voice="alloy" if bool(args.get("enable_tts", False)) else "",
                include_visuals=bool(args.get("include_visuals", True)),
            )
        )
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")
    return ok_result(
        name,
        f"已提交 AI 课堂生成任务，task_id={job.edu_job_id}",
        {"task_id": job.edu_job_id, "workflow_type": "classroom"},
    )
