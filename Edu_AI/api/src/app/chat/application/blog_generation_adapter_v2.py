from __future__ import annotations

import inspect

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

    def __init__(self, *, visual_pipeline=None, llm=None) -> None:
        self.visual_pipeline = visual_pipeline
        self.llm = llm

    def generate(self, payload, *, job_id: str, config_snapshot_id: str):
        course_id = str(getattr(payload, "course_id", "") or "").strip()
        topic = str(getattr(payload, "topic", "") or "").strip()
        if not course_id or not topic:
            raise ValueError("course_id and topic are required")
        body_llm = self.llm
        if body_llm is None:
            from app.chat.agents.report_generation import get_fallback_llm

            body_llm = get_fallback_llm()
        if body_llm is None:
            raise RuntimeError("blog_llm_unavailable")
        source_context = str(getattr(payload, "source_context", "") or "").strip()
        research_context = str(getattr(payload, "research_context", "") or "").strip()
        evidence_context = "\n\n".join(
            part for part in (source_context, research_context) if part
        )
        generation_config = {
            key: getattr(payload, key, None)
            for key in (
                "audience",
                "tone",
                "length",
                "structure",
                "special_requirements",
                "source_mode",
                "include_visuals",
            )
            if getattr(payload, key, None) not in (None, "")
        }
        if evidence_context:
            generation_config["source_context"] = evidence_context
        if research_context:
            generation_config["research_bundle_id"] = str(
                getattr(payload, "research_bundle_id", "") or ""
            )
        if bool(getattr(payload, "include_visuals", False)):
            pipeline = self.visual_pipeline
            llm = body_llm
            if pipeline is None:
                from app.chat.application.knowledge_base_direct_report_service_v2 import (
                    _build_default_visual_pipeline,
                )

                pipeline = _build_default_visual_pipeline()
            try:
                brief = pipeline.plan_with_model(
                    llm,
                    resource_type="blog",
                    topic=topic,
                    source_context=str(
                        getattr(payload, "source_context", "") or ""
                    ),
                )
                visual_result = pipeline.run(
                    brief,
                    course_id=course_id,
                    owner=str(getattr(payload, "owner", "") or "") or None,
                    selected_document_ids=list(
                        getattr(payload, "selected_doc_ids", []) or []
                    ),
                )
                generation_config["visual_plan"] = visual_result.to_snapshot()
            except Exception as exc:
                generation_config["visual_error"] = str(exc)
        create_task_state(
            thread_id=job_id,
            course_id=course_id,
            topic=topic,
            generation_config=generation_config,
        )
        for _ in range(3):
            if "llm" in inspect.signature(run_blog_task).parameters:
                run_blog_task(job_id, llm=body_llm)
            else:
                # Compatibility for injected legacy/test runners.
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

