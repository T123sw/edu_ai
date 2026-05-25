"""Agent tool handler: generate_report.

Calls build_report_markdown() directly via submit_callable_task.
WorkflowRuntime is NOT involved.
"""
from __future__ import annotations

from app.chat.runtime.agent_tools.handlers.outline_parser import parse_report_outline
from app.chat.runtime.agent_tools.result import error_result, ok_result


def handle_generate_report(name: str, args: dict, ctx) -> dict:
    subject = str(args.get("subject", "")).strip()
    confirmed_outline = str(args.get("confirmed_outline", "")).strip()
    focus = str(args.get("focus", "")).strip()
    length_hint = str(args.get("length_hint", "")).strip()

    if not subject:
        return error_result(name, "missing_subject", "报告主题不能为空")

    outline_chapters = parse_report_outline(confirmed_outline)

    allow_rag = bool(getattr(getattr(ctx, "capability", None), "allow_rag", False))
    selected_doc_ids = list(getattr(getattr(ctx, "capability", None), "selected_doc_ids", []) or [])
    owner = getattr(getattr(ctx, "request", None), "owner", None)

    def _run():
        from app.chat.agents.report_generation import build_report_markdown, get_fallback_llm
        from app.chat.skill_manager import SkillManager

        llm = get_fallback_llm()
        skill_manager = SkillManager()
        slots = {
            "core_topic": subject,
            "focus_area": focus,
            "length_requirement": length_hint,
        }
        body, checkpoint = build_report_markdown(
            skill_manager=skill_manager,
            slots=slots,
            outline=outline_chapters,
            mode="fast",
        )
        if body and allow_rag and selected_doc_ids:
            from app.chat.workflows.report.image_injector import inject_report_images_from_rag
            body = inject_report_images_from_rag(
                body,
                allow_rag=allow_rag,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
                query_text=subject,
            )
        return {
            "status": "completed",
            "artifacts": [{
                "artifact_type": "report",
                "title": subject,
                "content": body,
                "generation_state": checkpoint,
            }],
        }

    try:
        from app.chat.tasks.background_runner import submit_callable_task
        task_id = submit_callable_task(fn=_run, workflow_type="report")
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交报告生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "report"},
    )
