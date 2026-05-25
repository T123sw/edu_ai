"""Agent tool handler: generate_ppt.

Pipeline: Markdown outline → PptOutline → PptContentMarkdownGenerator → Html2PptClient.
All engine imports deferred inside _run() to avoid circular imports at load time.
"""
from __future__ import annotations
import os

from app.chat.runtime.agent_tools.handlers.outline_parser import parse_ppt_slides
from app.chat.runtime.agent_tools.result import error_result, ok_result


def handle_generate_ppt(name: str, args: dict, ctx) -> dict:
    topic = str(args.get("topic", "")).strip()
    confirmed_outline = str(args.get("confirmed_outline", "")).strip()
    slide_count = int(args.get("slide_count") or 10)

    if not topic:
        return error_result(name, "missing_topic", "PPT 主题不能为空")

    raw_slides = parse_ppt_slides(confirmed_outline)
    if not raw_slides:
        return error_result(name, "outline_parse_failed", "PPT 大纲解析失败，请确认大纲格式（用 ## 作为每页标题）")

    def _run():
        from app.chat.agents.report_generation import get_fallback_llm
        from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide
        from app.chat.workflows.ppt.content_markdown_generator import PptContentMarkdownGenerator
        from app.chat.workflows.ppt.html2ppt_client import Html2PptClient

        slides = _build_ppt_slides(raw_slides)
        ppt_outline = PptOutline(
            deck_title=topic,
            slides=slides,
            confirmation_status="confirmed",
        )

        generator = PptContentMarkdownGenerator(llm=get_fallback_llm())
        content_md, _debug = generator.generate(outline=ppt_outline)

        client = Html2PptClient(
            base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
        )
        job = client.create_job(
            content_markdown=content_md,
            theme_id=ppt_outline.theme_id,
            metadata={"topic": topic, "slide_count": slide_count, "source": "agent"},
        )
        job_id = job.get("job_id", "")
        return {
            "status": "completed",
            "artifacts": [{
                "artifact_type": "ppt",
                "title": topic,
                "job_id": job_id,
            }],
        }

    try:
        from app.chat.tasks.background_runner import submit_callable_task
        task_id = submit_callable_task(fn=_run, workflow_type="ppt")
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交 PPT 生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "ppt"},
    )


def _build_ppt_slides(raw_slides: list[dict]):
    """Convert [{title, bullets}] → list[PptOutlineSlide] with role assignment."""
    from app.chat.domain.ppt_outline import PptOutlineSlide

    total = len(raw_slides)
    result = []
    for i, slide in enumerate(raw_slides):
        if i == 0:
            role = "title"
        elif i == total - 1:
            role = "summary"
        else:
            role = "content"
        result.append(PptOutlineSlide(
            slide_index=i,
            role=role,
            title=slide["title"],
            goal=f"介绍{slide['title']}",
            key_points=slide.get("bullets") or [],
        ))
    return result
