from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
from types import SimpleNamespace

from app.auth import get_current_user
from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.workspace_scope import SCOPE_TYPE_COURSE, collect_scope_ids_for_query
from core.conversation_storage import conversation_storage
from core.auth import auth_manager
from core.course_storage import storage_manager

from .schemas import ChatRequest, ChatResponse, SkillHealthCheckRequest, SkillHealthCheckResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])
FLAGS = None
service = None
reply_service_v2 = None
_status_card_builder = None
_context_builder = None


def _get_flags():
    global FLAGS
    if FLAGS is None:
        from .application.route_feature_flags import load_route_feature_flags

        FLAGS = load_route_feature_flags()
    return FLAGS


def _get_service():
    global service
    if service is None:
        from .application.route_service_factory import build_default_route_chat_service

        service = build_default_route_chat_service()
    return service


def _get_status_card_builder():
    global _status_card_builder
    if _status_card_builder is None:
        _status_card_builder = StatusCardBuilder()
    return _status_card_builder


def _get_reply_service_v2():
    global reply_service_v2
    if reply_service_v2 is None:
        from app.chat.application.reply_service_v2 import build_default_reply_service_v2

        reply_service_v2 = build_default_reply_service_v2()
    return reply_service_v2


def _get_context_builder():
    global _context_builder
    if _context_builder is None:
        _context_builder = ContextBuilder(
            conversation_store=ConversationStoreAdapter(storage=conversation_storage)
        )
    return _context_builder


def _build_status_card_for_conversation(conversation_id: str, owner: str | None):
    state = conversation_storage.get_state(conversation_id)
    active_context = dict(state.get("active_context") or {})
    capability_state = dict(state.get("capability_policy") or {})
    selected_doc_ids = list(
        capability_state.get("selected_doc_ids")
        or active_context.get("pinned_doc_ids")
        or []
    )
    _allow_web = bool(capability_state.get("allow_web", False))
    capability = CapabilityPolicy(
        allow_rag=bool(capability_state.get("allow_rag")) or bool(selected_doc_ids),
        allow_web=_allow_web,
        # Phase 6-A.2: image_search default True; planner gates real usage.
        # planner-side keyword detection still gates actual invocation.
        allow_image_search=bool(capability_state.get("allow_image_search", True)),
        selected_doc_ids=selected_doc_ids,
    )
    request = SimpleNamespace(
        conversation_id=conversation_id,
        owner=owner,
        capability=capability,
    )
    snapshot = _get_context_builder().build(request)
    card = _get_status_card_builder().build(
        snapshot=snapshot,
        workflow=None,
        capability=capability,
    )
    return card.model_dump(exclude_none=True)


def _maybe_refresh_running_ppt_edit_conversation(conversation_id: str, owner: str | None):
    get_state = getattr(conversation_storage, "get_state", None)
    if not callable(get_state):
        return None

    state = get_state(conversation_id)
    workflow_state = dict(state.get("workflow_state") or {})
    if str(workflow_state.get("workflow_type") or "").strip() != "ppt":
        return None
    if str(workflow_state.get("status") or "").strip() != "running":
        return None
    if str(workflow_state.get("stage") or "").strip() != "polling_revision":
        return None

    artifact_reference = dict(state.get("artifact_reference") or {})
    if str(artifact_reference.get("artifact_type") or "").strip() != "ppt_deck":
        return None

    active_context = dict(state.get("active_context") or {})
    capability_state = dict(state.get("capability_policy") or {})
    selected_doc_ids = list(capability_state.get("selected_doc_ids") or [])
    request = SimpleNamespace(
        question="",
        conversation_id=conversation_id,
        owner=owner,
        course_id=active_context.get("current_course_id"),
        capability=CapabilityPolicy(
            allow_rag=bool(capability_state.get("allow_rag")),
            allow_web=bool(capability_state.get("allow_web")),
            # Phase 6-A.2: image_search default True; planner gates real usage.
            allow_image_search=bool(capability_state.get("allow_image_search", True)),
            selected_doc_ids=selected_doc_ids,
        ),
        artifact_reference=SimpleNamespace(**artifact_reference),
    )
    return _get_reply_service_v2().refresh_running_conversation(request)


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    t0 = time.perf_counter()
    cid = str(payload.conversation_id or "new")[-8:]
    username = current_user.get("username", "?")
    q_preview = str(payload.question or "")[:50]
    print(f"[CHAT {cid}] start | user={username} | q=\"{q_preview}\"", flush=True)
    try:
        data = _get_service().chat(
            question=payload.question,
            conversation_id=payload.conversation_id,
            model_id=payload.model_id,
            use_rag=bool(payload.use_rag),
            allow_rag=bool(payload.allow_rag),
            selected_doc_ids=payload.selected_doc_ids,
            owner=current_user.get("username"),
            course_id=payload.course_id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            allow_web=bool(payload.allow_web),
            action_hint=payload.action_hint,
            artifact_id=payload.artifact_id,
        )
        print(f"[CHAT {cid}] done {(time.perf_counter() - t0) * 1000:.0f}ms", flush=True)
        return ChatResponse(**data)
    except Exception as exc:
        print(f"[CHAT {cid}] fail {(time.perf_counter() - t0) * 1000:.0f}ms | {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"聊天失败: {exc}") from exc


@router.get("/stream")
async def chat_stream(
    question: str,
    conversation_id: str | None = None,
    model_id: str | None = None,
    use_rag: bool = False,
    allow_rag: bool | None = None,
    allow_web: bool = False,
    action_hint: str | None = None,
    selected_doc_ids: str | None = None,
    course_id: str | None = None,
    scope_type: str = SCOPE_TYPE_COURSE,
    scope_id: str | None = None,
    token: str | None = None,
):
    try:
        if not token:
            raise HTTPException(status_code=401, detail="缺少token")
        current_user = auth_manager.get_current_user(token)
    except HTTPException as exc:
        raise exc

    async def event_generator():
        t0 = time.perf_counter()
        cid = str(conversation_id or "new")[-8:]
        username = current_user.get("username", "?")
        q_preview = str(question or "")[:50]
        print(f"[STREAM {cid}] start | user={username} | q=\"{q_preview}\"", flush=True)
        try:
            parsed_doc_ids = None
            if selected_doc_ids:
                parsed_doc_ids = [doc_id for doc_id in selected_doc_ids.split(",") if doc_id]

            meta, stream = _get_service().chat_stream_with_meta(
                question=question,
                conversation_id=conversation_id,
                model_id=model_id,
                use_rag=bool(use_rag),
                allow_rag=allow_rag,
                selected_doc_ids=parsed_doc_ids,
                owner=current_user.get("username"),
                course_id=course_id,
                scope_type=scope_type,
                scope_id=scope_id,
                allow_web=bool(allow_web),
                action_hint=action_hint,
            )
            from .application.response_builder import build_legacy_sse_frames

            first_delta = True
            delta_count = 0
            for frame in build_legacy_sse_frames(meta, stream, include_v2=_get_flags().enable_sse_v2_events):
                if frame.startswith("event: delta"):
                    delta_count += 1
                    if first_delta:
                        first_delta = False
                        print(f"[STREAM {cid}] ttft {(time.perf_counter() - t0) * 1000:.0f}ms", flush=True)
                yield frame
                await asyncio.sleep(0)

            print(
                f"[STREAM {cid}] ← 完成 {(time.perf_counter() - t0) * 1000:.0f}ms"
                f" | {delta_count} frames",
                flush=True,
            )
        except Exception as exc:
            print(f"[STREAM {cid}] fail {(time.perf_counter() - t0) * 1000:.0f}ms | {exc}", flush=True)
            yield f"event: error\ndata: {str(exc)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers=headers,
    )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: dict = Depends(get_current_user)):
    from app.chat.tasks.task_store import get_task_store

    task = get_task_store().get(
        task_id,
        owner_user_id=str(current_user.get("username") or "").strip(),
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return task


@router.post("/skill-health-check", response_model=SkillHealthCheckResponse)
async def skill_health_check(payload: SkillHealthCheckRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    try:
        result = _get_service().skill_health_check(payload.meta)
        return SkillHealthCheckResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"技能健康检查失败: {exc}") from exc


@router.get("/conversations")
async def list_conversations(
    course_id: str | None = None,
    scope_type: str = SCOPE_TYPE_COURSE,
    scope_id: str | None = None,
    aggregate: bool = False,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    if not course_id and not aggregate and limit == 20 and offset == 0:
        return conversation_storage.list_conversations(owner=current_user.get("username"))

    scope_ids = None
    effective_scope_type = scope_type if course_id else None
    if course_id and scope_type == "knowledge_point":
        graph_root = storage_manager.get_knowledge_graph(course_id)
        scope_ids = collect_scope_ids_for_query(
            graph_root,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    return conversation_storage.list_conversations(
        owner=current_user.get("username"),
        course_id=course_id,
        scope_type=effective_scope_type,
        scope_ids=scope_ids,
        aggregate=aggregate,
        limit=limit,
        offset=offset,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    try:
        _maybe_refresh_running_ppt_edit_conversation(
            conversation_id,
            current_user.get("username"),
        )
        payload = conversation_storage.get_conversation(conversation_id, owner=current_user.get("username"))
        payload["status_card"] = _build_status_card_for_conversation(
            conversation_id,
            current_user.get("username"),
        )
        return payload
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    try:
        conversation_storage.delete_conversation(conversation_id, owner=current_user.get("username"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc
    return {"message": "对话历史已删除"}
