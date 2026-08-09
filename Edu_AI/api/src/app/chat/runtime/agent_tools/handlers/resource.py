"""Agent handlers for resources that do not require outline confirmation."""
from __future__ import annotations

from uuid import uuid4

from app.chat.runtime.agent_tools.handlers.report import _collect_research_evidence
from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.generation_command import GenerationCommand, generation_command_service


def _source_scope(ctx) -> tuple[bool, list[str], str]:
    capability = getattr(ctx, "capability", None)
    allow_rag = bool(getattr(capability, "allow_rag", False))
    selected_doc_ids = list(getattr(capability, "selected_doc_ids", []) or [])
    source_mode = (
        "selected_documents"
        if selected_doc_ids
        else ("course_auto" if allow_rag else "none")
    )
    return allow_rag, selected_doc_ids, source_mode


def _resource_config(resource_type: str, args: dict) -> dict:
    topic = str(args.get("topic") or args.get("title") or "").strip()
    if resource_type == "blog":
        return {
            "title": topic,
            "topic": topic,
            "audience": str(args.get("audience") or "教师").strip(),
            "tone": str(args.get("tone") or "popular").strip(),
            "length": str(args.get("length") or "medium").strip(),
            "structure": str(args.get("structure") or "").strip(),
            "special_requirements": str(args.get("special_requirements") or "").strip(),
            "include_visuals": bool(args.get("include_visuals", False)),
        }
    if resource_type == "flashcard":
        return {
            "title": topic,
            "flashcard_config": {
                "title": topic,
                "count": max(3, min(30, int(args.get("count") or 10))),
                "difficulty": str(args.get("difficulty") or "medium"),
                "category": str(args.get("category") or "").strip(),
                "show_sources": bool(args.get("show_sources", True)),
            },
        }
    if resource_type == "graph":
        return {
            "title": topic,
            "description": str(args.get("description") or "").strip(),
            "max_depth": max(2, min(5, int(args.get("max_depth") or 3))),
        }
    if resource_type == "game":
        return {
            "title": topic,
            "topic": topic,
            "game_type": str(args.get("game_type") or "drag_match"),
            "card_count": max(4, min(30, int(args.get("card_count") or 8))),
            "difficulty": str(args.get("difficulty") or "medium"),
            "duration_minutes": max(
                1, min(60, int(args.get("duration_minutes") or 5))
            ),
        }
    raise ValueError(f"unsupported resource type: {resource_type}")


def handle_generate_resource(name: str, args: dict, ctx) -> dict:
    resource_type = name.removeprefix("generate_")
    topic = str(args.get("topic") or args.get("title") or "").strip()
    if not topic:
        return error_result(name, "missing_topic", "资源主题不能为空")

    allow_rag, selected_doc_ids, source_mode = _source_scope(ctx)
    research_context, research_sources = _collect_research_evidence(ctx)
    request = getattr(ctx, "request", None)
    config = {
        "entrypoint": "agent",
        **_resource_config(resource_type, args),
        "allow_rag": allow_rag,
        "research_context": research_context,
        "research_sources": research_sources,
    }
    try:
        command = GenerationCommand(
            resource_type=resource_type,
            owner_user_id=str(getattr(request, "owner", None) or ""),
            course_id=str(getattr(request, "course_id", None) or ""),
            scope_type=str(getattr(request, "scope_type", None) or "course"),
            scope_id=getattr(request, "scope_id", None),
            source_mode=source_mode,
            selected_doc_ids=selected_doc_ids,
            config=config,
            idempotency_key=f"agent-{resource_type}-{uuid4()}",
        )
        job = generation_command_service.submit(command)
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交{resource_type}生成任务，task_id={job.edu_job_id}",
        {"task_id": job.edu_job_id, "workflow_type": resource_type},
    )
