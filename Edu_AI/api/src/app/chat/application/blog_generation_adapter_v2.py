from __future__ import annotations

from app.blog_agent.engine import run_blog_task
from app.blog_agent.storage import (
    create_task_state,
    load_task_state,
    save_task_state,
)


class BlogGenerationAdapterV2:
    """Run the existing HITL blog engine with its generated outlines accepted.

    The generation-factory flow is intentionally non-blocking, so its configured
    topic is treated as approval to proceed. The dedicated legacy blog screen can
    still use manual outline review.
    """

    def generate(self, payload, *, job_id: str, config_snapshot_id: str):
        course_id = str(getattr(payload, "course_id", "") or "").strip()
        topic = str(getattr(payload, "topic", "") or "").strip()
        if not course_id or not topic:
            raise ValueError("course_id and topic are required")
        create_task_state(thread_id=job_id, course_id=course_id, topic=topic)
        for _ in range(3):
            run_blog_task(job_id)
            state = load_task_state(job_id)
            if state is None:
                raise RuntimeError("blog task state was lost")
            if state.status == "waiting_for_chapter_review":
                state.pending_chapters = list(state.outline or [])
                save_task_state(state)
                continue
            if state.status == "waiting_for_outline_review":
                state.pending_outline = list(state.outline or [])
                save_task_state(state)
                continue
            if state.status == "completed":
                saved = not str(state.error_message or "").startswith("保存教学博客")
                return {
                    "saved": saved,
                    "error": None if saved else state.error_message,
                    "result_ref": {
                        "resource_type": "course_material" if saved else "generated_artifact",
                        "course_id": course_id,
                        "material_type": "blog",
                        "material_id": job_id,
                    },
                }
            if state.status == "failed":
                raise RuntimeError(state.error_message or "教学博客生成失败")
        raise RuntimeError("教学博客未能通过大纲阶段")

