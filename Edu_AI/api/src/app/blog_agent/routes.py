from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import get_current_user

from .engine import run_blog_task
from .models import (
    BlogGenerateStartRequest,
    BlogGenerateStartResponse,
    BlogResumeChaptersRequest,
    BlogResumeOutlineRequest,
    BlogTaskStatusResponse,
)
from .storage import create_task_state, load_task_state, save_task_state


router = APIRouter(tags=["教学博客Agent"])


@router.post("/generate/start", response_model=BlogGenerateStartResponse, summary="启动教学博客生成任务")
async def start_blog_generate(
    payload: BlogGenerateStartRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    # 当前MVP不做权限隔离，先保证任务可跑通；后续可按 owner 分目录存储
    import uuid

    thread_id = f"blog_{uuid.uuid4().hex}"
    create_task_state(thread_id=thread_id, course_id=payload.course_id, topic=payload.topic)

    background_tasks.add_task(run_blog_task, thread_id)

    return BlogGenerateStartResponse(thread_id=thread_id)


@router.get("/task/{thread_id}/status", response_model=BlogTaskStatusResponse, summary="查询教学博客任务状态")
async def get_blog_task_status(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    state = load_task_state(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return BlogTaskStatusResponse(
        thread_id=state.thread_id,
        status=state.status,
        progress=state.progress,
        outline=state.outline or None,
        final_markdown=state.final_markdown,
        error_message=state.error_message,
    )


@router.post(
    "/task/{thread_id}/resume-chapters",
    response_model=BlogTaskStatusResponse,
    summary="人工审查后恢复教学博客任务（一级目录：章节）",
)
async def resume_blog_task_chapters(
    thread_id: str,
    payload: BlogResumeChaptersRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    state = load_task_state(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if state.status != "waiting_for_chapter_review":
        raise HTTPException(status_code=400, detail=f"任务当前状态不允许恢复章节审查: {state.status}")

    state.pending_chapters = payload.chapters
    save_task_state(state)

    background_tasks.add_task(run_blog_task, thread_id)

    state = load_task_state(thread_id)
    return BlogTaskStatusResponse(
        thread_id=state.thread_id,
        status=state.status,
        progress=state.progress,
        outline=state.outline or None,
        final_markdown=state.final_markdown,
        error_message=state.error_message,
    )


@router.post(
    "/task/{thread_id}/resume-outline",
    response_model=BlogTaskStatusResponse,
    summary="人工审查后恢复教学博客任务（二级目录：章节+小标题）",
)
async def resume_blog_task_outline(
    thread_id: str,
    payload: BlogResumeOutlineRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    state = load_task_state(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if state.status != "waiting_for_outline_review":
        raise HTTPException(status_code=400, detail=f"任务当前状态不允许恢复大纲审查: {state.status}")

    state.pending_outline = payload.outline
    save_task_state(state)

    background_tasks.add_task(run_blog_task, thread_id)

    state = load_task_state(thread_id)
    return BlogTaskStatusResponse(
        thread_id=state.thread_id,
        status=state.status,
        progress=state.progress,
        outline=state.outline or None,
        final_markdown=state.final_markdown,
        error_message=state.error_message,
    )

