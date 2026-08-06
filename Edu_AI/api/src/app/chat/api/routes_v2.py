from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.auth import get_current_user
from app.chat.api.schemas_v2 import (
    ChatDirectTaskSubmittedResponseV2,
    ChatQuizPrefillResponseV2,
    ChatLessonPlanCardsRequestV2,
    ChatLessonPlanCardsResponseV2,
    ChatPptCardsRequestV2,
    ChatPptCardsResponseV2,
    ChatReplyRequestV2,
    ChatReportCardsRequestV2,
    ChatReportCardsResponseV2,
    ChatReportRequestV2,
    ChatResponseV2,
    KnowledgeBaseDirectQuizPrefillRequestV2,
    KnowledgeBaseDirectQuizRequestV2,
    KnowledgeBaseDirectGameRequestV2,
    KnowledgeBaseDirectFlashcardRequestV2,
    KnowledgeBaseDirectPptGenerateRequestV2,
    KnowledgeBaseDirectPptOutlineRequestV2,
    KnowledgeBaseDirectGraphRequestV2,
    KnowledgeBaseDirectBlogRequestV2,
    KnowledgeBaseDirectReportRequestV2,
)
from app.chat.application.response_builder_v2 import build_v2_error_response
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from core.config import Config


router = APIRouter(prefix="/api/chat/v2", tags=["chat-v2"])


def _get_reply_service():
    from app.chat.application.reply_service_v2 import build_default_reply_service_v2

    return build_default_reply_service_v2()


def _get_report_service():
    from app.chat.application.report_service_v2 import build_default_report_service_v2

    return build_default_report_service_v2()


def _get_report_entry_cards_service():
    from app.chat.application.report_entry_cards_service_v2 import build_default_report_entry_cards_service_v2

    return build_default_report_entry_cards_service_v2()


def _get_direct_report_service():
    from app.chat.application.knowledge_base_direct_report_service_v2 import (
        build_default_knowledge_base_direct_report_service_v2,
    )

    return build_default_knowledge_base_direct_report_service_v2()


def _get_direct_quiz_service():
    from app.chat.application.knowledge_base_direct_quiz_service_v2 import (
        build_default_knowledge_base_direct_quiz_service_v2,
    )

    return build_default_knowledge_base_direct_quiz_service_v2()


def _get_direct_game_service():
    from app.chat.application.knowledge_base_direct_game_service_v2 import (
        build_default_knowledge_base_direct_game_service_v2,
    )

    return build_default_knowledge_base_direct_game_service_v2()


def _get_direct_flashcard_service():
    from app.chat.application.knowledge_base_direct_flashcard_service_v2 import (
        build_default_knowledge_base_direct_flashcard_service_v2,
    )

    return build_default_knowledge_base_direct_flashcard_service_v2()


def _get_direct_ppt_service():
    from app.chat.application.knowledge_base_direct_ppt_service_v2 import (
        build_default_knowledge_base_direct_ppt_service_v2,
    )

    return build_default_knowledge_base_direct_ppt_service_v2()


def _get_ppt_entry_cards_service():
    from app.chat.application.ppt_entry_cards_service_v2 import build_default_ppt_entry_cards_service_v2

    return build_default_ppt_entry_cards_service_v2()


def _get_lesson_plan_entry_cards_service():
    from app.chat.application.lesson_plan_entry_cards_service_v2 import (
        build_default_lesson_plan_entry_cards_service_v2,
    )

    return build_default_lesson_plan_entry_cards_service_v2()


def _with_owner(payload, current_user: dict):
    data = payload.model_dump()
    data["owner"] = current_user.get("username")
    return SimpleNamespace(**data)


def _stream_json_frame(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _is_workflow_intent_from_reply(payload: ChatReplyRequestV2) -> bool:
    question = str(payload.question or "")
    if payload.action_hint in {"generate.report", "generate.ppt", "generate.lesson_plan", "generate.quiz"}:
        return True
    lowered = question.lower()
    if any(token in lowered for token in ("ppt", "quiz", "report", "lesson plan", "exercise", "practice", "test")):
        return True
    return any(token in question for token in ("报告", "课件", "教案", "习题", "练习题", "测试题"))


def _is_report_intent_from_reply(payload: ChatReplyRequestV2) -> bool:
    question = str(payload.question or "")
    return payload.action_hint == "generate.report" or "报告" in question


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return cleaned or fallback


def _chat_images_root() -> Path:
    root = (Config.STORAGE_ROOT / "chat_images").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _chat_videos_root() -> Path:
    root = (Config.STORAGE_ROOT / "chat_videos").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _chat_games_root() -> Path:
    root = (Config.STORAGE_ROOT / "chat_games").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_chat_image_url(relative_path: str) -> str:
    return f"/api/chat/v2/images?path={quote(relative_path, safe='')}"


def _build_chat_video_url(relative_path: str) -> str:
    return f"/api/chat/v2/videos?path={quote(relative_path, safe='')}"


def _build_chat_game_url(relative_path: str) -> str:
    return f"/api/chat/v2/games/html?path={quote(relative_path, safe='')}"


def _resolve_chat_image_path(*, owner: str, relative_path: str) -> Path:
    root = _chat_images_root()
    requested = (root / str(relative_path or "")).resolve()
    expected_owner_root = (root / _safe_segment(owner, "anonymous")).resolve()
    if not str(requested).startswith(str(expected_owner_root)):
        raise HTTPException(status_code=403, detail="forbidden_image_path")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="image_not_found")
    return requested


def _resolve_chat_video_path(*, owner: str, relative_path: str) -> Path:
    root = _chat_videos_root()
    requested = (root / str(relative_path or "")).resolve()
    expected_owner_root = (root / _safe_segment(owner, "anonymous")).resolve()
    if not str(requested).startswith(str(expected_owner_root)):
        raise HTTPException(status_code=403, detail="forbidden_video_path")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="video_not_found")
    return requested


def _resolve_chat_game_path(*, owner: str, relative_path: str) -> Path:
    root = _chat_games_root()
    requested = (root / str(relative_path or "")).resolve()
    expected_owner_root = (root / _safe_segment(owner, "anonymous")).resolve()
    if not str(requested).startswith(str(expected_owner_root)):
        raise HTTPException(status_code=403, detail="forbidden_game_path")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="game_not_found")
    return requested


@router.post("/images/upload")
async def upload_chat_images(
    files: list[UploadFile] = File(...),
    conversation_id: str | None = Form(default=None),
    source: str = Form(default="upload"),
    current_user: dict = Depends(get_current_user),
):
    owner = _safe_segment(str(current_user.get("username") or ""), "anonymous")
    session_id = _safe_segment(conversation_id or f"session-{uuid4().hex[:12]}", "session")
    target_dir = _chat_images_root() / owner / session_id
    target_dir.mkdir(parents=True, exist_ok=True)

    images: list[dict] = []
    for upload in files:
        mime_type = str(upload.content_type or "").strip().lower()
        if not mime_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"unsupported_image_type:{mime_type or 'unknown'}")

        original_name = Path(str(upload.filename or "image")).name or "image"
        suffix = Path(original_name).suffix or mimetypes.guess_extension(mime_type) or ".png"
        stored_name = f"{uuid4().hex[:12]}_{Path(original_name).stem}{suffix}"
        target_path = (target_dir / stored_name).resolve()
        target_path.write_bytes(await upload.read())

        relative_path = target_path.relative_to(_chat_images_root()).as_posix()
        images.append(
            {
                "image_id": uuid4().hex[:12],
                "file_name": original_name,
                "mime_type": mime_type or "image/png",
                "storage_path": str(target_path),
                "relative_path": relative_path,
                "image_url": _build_chat_image_url(relative_path),
                "source": "paste" if str(source).strip().lower() == "paste" else "upload",
            }
        )

    return {
        "conversation_id": conversation_id or "",
        "session_id": session_id,
        "images": images,
    }


@router.get("/images")
async def get_chat_image(
    path: str = Query(..., description="Relative chat image path under storage/chat_images"),
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "")
    resolved = _resolve_chat_image_path(owner=owner, relative_path=unquote(path))
    media_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    return FileResponse(path=str(resolved), media_type=media_type, filename=resolved.name)


@router.post("/videos/upload")
async def upload_chat_videos(
    files: list[UploadFile] = File(...),
    conversation_id: str | None = Form(default=None),
    source: str = Form(default="upload"),
    current_user: dict = Depends(get_current_user),
):
    owner = _safe_segment(str(current_user.get("username") or ""), "anonymous")
    session_id = _safe_segment(conversation_id or f"session-{uuid4().hex[:12]}", "session")
    target_dir = _chat_videos_root() / owner / session_id
    target_dir.mkdir(parents=True, exist_ok=True)

    videos: list[dict] = []
    for upload in files:
        mime_type = str(upload.content_type or "").strip().lower()
        if not mime_type.startswith("video/"):
            raise HTTPException(status_code=400, detail=f"unsupported_video_type:{mime_type or 'unknown'}")

        original_name = Path(str(upload.filename or "video")).name or "video"
        suffix = Path(original_name).suffix or mimetypes.guess_extension(mime_type) or ".mp4"
        stored_name = f"{uuid4().hex[:12]}_{Path(original_name).stem}{suffix}"
        target_path = (target_dir / stored_name).resolve()
        target_path.write_bytes(await upload.read())

        relative_path = target_path.relative_to(_chat_videos_root()).as_posix()
        videos.append(
            {
                "video_id": uuid4().hex[:12],
                "file_name": original_name,
                "mime_type": mime_type or "video/mp4",
                "storage_path": str(target_path),
                "relative_path": relative_path,
                "video_url": _build_chat_video_url(relative_path),
                "source": "upload" if str(source).strip().lower() == "upload" else "upload",
            }
        )

    return {
        "conversation_id": conversation_id or "",
        "session_id": session_id,
        "videos": videos,
    }


@router.get("/videos")
async def get_chat_video(
    path: str = Query(..., description="Relative chat video path under storage/chat_videos"),
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "")
    resolved = _resolve_chat_video_path(owner=owner, relative_path=unquote(path))
    media_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    return FileResponse(path=str(resolved), media_type=media_type, filename=resolved.name)


@router.get("/games/html")
async def get_chat_game(
    path: str = Query(..., description="Relative chat game html path under storage/chat_games"),
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "")
    resolved = _resolve_chat_game_path(owner=owner, relative_path=unquote(path))
    return FileResponse(path=str(resolved), media_type="text/html", filename=resolved.name)


@router.post("/reply", response_model=ChatResponseV2)
async def reply(payload: ChatReplyRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_reply_service().reply(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id=payload.conversation_id or "",
            trace_path="workflow" if _is_workflow_intent_from_reply(payload) else "fast",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/stream")
async def stream_reply(payload: ChatReplyRequestV2, current_user: dict = Depends(get_current_user)):
    def generate():
        try:
            for event in _get_reply_service().reply_stream(_with_owner(payload, current_user)):
                yield _stream_json_frame(event)
        except Exception as exc:
            yield _stream_json_frame(
                {
                    "type": "error",
                    "payload": {
                        "message": str(exc),
                        "conversation_id": payload.conversation_id or "",
                    },
                }
            )

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/report", response_model=ChatResponseV2)
async def report(payload: ChatReportRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_report_service().report(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id=payload.conversation_id or "",
            trace_path="workflow",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/report/cards", response_model=ChatReportCardsResponseV2)
async def report_cards(payload: ChatReportCardsRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_report_entry_cards_service().get_cards(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="workflow",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/ppt/cards", response_model=ChatPptCardsResponseV2)
async def ppt_cards(payload: ChatPptCardsRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_ppt_entry_cards_service().get_cards(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/lesson-plan/cards", response_model=ChatLessonPlanCardsResponseV2)
async def lesson_plan_cards(payload: ChatLessonPlanCardsRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_lesson_plan_entry_cards_service().get_cards(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/report/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_report(payload: KnowledgeBaseDirectReportRequestV2, current_user: dict = Depends(get_current_user)):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="report",
        owner_user_id=owner,
        course_id=str(payload.course_id or ""),
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={
            "title": payload.question[:160],
            "question": payload.question,
            "report_config": payload.report_config,
            "prompt_draft": payload.prompt_draft,
            "final_user_prompt": payload.final_user_prompt,
            "selected_card": (
                payload.selected_card.model_dump(mode="json")
                if payload.selected_card is not None
                else None
            ),
        },
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    job = generation_command_service.submit(command)
    return {"task_id": job.edu_job_id, "status": "pending", "workflow_type": "report_direct"}


@router.post("/quiz/prefill", response_model=ChatQuizPrefillResponseV2)
async def quiz_prefill(payload: KnowledgeBaseDirectQuizPrefillRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_direct_quiz_service().prefill(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/quiz/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_quiz(payload: KnowledgeBaseDirectQuizRequestV2, current_user: dict = Depends(get_current_user)):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="quiz",
        owner_user_id=owner,
        course_id=str(payload.course_id or ""),
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={
            "title": payload.quiz_config.topic[:160],
            "quiz_config": payload.quiz_config.model_dump(mode="json"),
            "prompt_draft": payload.prompt_draft,
            "final_user_prompt": payload.final_user_prompt,
        },
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    job = generation_command_service.submit(command)
    return {"task_id": job.edu_job_id, "status": "pending", "workflow_type": "quiz_direct"}


@router.post("/game/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_game(payload: KnowledgeBaseDirectGameRequestV2, current_user: dict = Depends(get_current_user)):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="game",
        owner_user_id=owner,
        course_id=str(payload.course_id or ""),
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={
            "title": f"{payload.game_type} 小游戏",
            "game_type": payload.game_type,
        },
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    job = generation_command_service.submit(command)
    return {"task_id": job.edu_job_id, "status": "pending", "workflow_type": "game_direct"}


@router.post("/flashcard/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_flashcard(
    payload: KnowledgeBaseDirectFlashcardRequestV2,
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="flashcard",
        owner_user_id=owner,
        course_id=payload.course_id,
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={
            "title": payload.flashcard_config.title,
            "flashcard_config": payload.flashcard_config.model_dump(mode="json"),
        },
        idempotency_key=payload.idempotency_key,
    )
    job = generation_command_service.submit(command)
    return {
        "task_id": job.edu_job_id,
        "status": "pending",
        "workflow_type": "flashcard_direct",
    }


@router.post("/ppt/outline")
async def direct_ppt_outline(
    payload: KnowledgeBaseDirectPptOutlineRequestV2,
    current_user: dict = Depends(get_current_user),
):
    request = _with_owner(payload, current_user)
    return _get_direct_ppt_service().generate_outline(request)


@router.post("/ppt/generate", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_ppt_generate(
    payload: KnowledgeBaseDirectPptGenerateRequestV2,
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "").strip()
    service = _get_direct_ppt_service()
    try:
        draft = service.get_draft(owner=owner, draft_id=payload.draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ppt_draft_not_found") from exc
    command = GenerationCommand(
        resource_type="ppt",
        owner_user_id=owner,
        course_id=str(draft.get("course_id") or ""),
        scope_type=str(draft.get("scope_type") or "course"),
        scope_id=draft.get("scope_id"),
        source_mode=str(
            draft.get("source_mode")
            or (
                "selected_documents"
                if draft.get("selected_doc_ids")
                else "course_auto"
            )
        ),
        selected_doc_ids=list(draft.get("selected_doc_ids") or []),
        config={
            **dict(draft.get("normalized_ppt_config") or {}),
            "title": str(
                dict(draft.get("normalized_ppt_config") or {}).get("deck_title")
                or "PPT"
            ),
            "draft_id": payload.draft_id,
            "confirm": payload.confirm,
            "outline": payload.outline,
        },
        idempotency_key=payload.idempotency_key,
    )
    job = generation_command_service.submit(command)
    return {
        "task_id": job.edu_job_id,
        "status": "pending",
        "workflow_type": "ppt_direct",
    }


@router.post("/graph/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_graph(
    payload: KnowledgeBaseDirectGraphRequestV2,
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="graph",
        owner_user_id=owner,
        course_id=payload.course_id,
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={"title": payload.title, "max_depth": payload.max_depth},
        idempotency_key=payload.idempotency_key,
    )
    job = generation_command_service.submit(command)
    return {"task_id": job.edu_job_id, "status": "pending", "workflow_type": "graph_direct"}


@router.post("/blog/direct", response_model=ChatDirectTaskSubmittedResponseV2, status_code=202)
async def direct_blog(
    payload: KnowledgeBaseDirectBlogRequestV2,
    current_user: dict = Depends(get_current_user),
):
    owner = str(current_user.get("username") or "").strip()
    command = GenerationCommand(
        resource_type="blog",
        owner_user_id=owner,
        course_id=payload.course_id,
        scope_type=payload.scope_type or "course",
        scope_id=payload.scope_id,
        source_mode=payload.source_mode,
        selected_doc_ids=payload.selected_doc_ids,
        config={"title": payload.topic, "topic": payload.topic},
        idempotency_key=payload.idempotency_key,
    )
    job = generation_command_service.submit(command)
    return {"task_id": job.edu_job_id, "status": "pending", "workflow_type": "blog_direct"}

