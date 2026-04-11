from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.auth import get_current_user
from app.chat.api.schemas_v2 import (
    ChatDirectPptGenerateResponseV2,
    ChatDirectPptOutlineResponseV2,
    ChatPptCardsRequestV2,
    ChatPptCardsResponseV2,
    ChatDirectReportResponseV2,
    ChatReplyRequestV2,
    ChatReportCardsRequestV2,
    ChatReportCardsResponseV2,
    ChatReportRequestV2,
    ChatResponseV2,
    KnowledgeBaseDirectPptGenerateRequestV2,
    KnowledgeBaseDirectPptOutlineRequestV2,
    KnowledgeBaseDirectReportRequestV2,
)
from app.chat.application.response_builder_v2 import build_v2_error_response


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


def _get_direct_ppt_outline_service():
    from app.chat.application.knowledge_base_direct_ppt_outline_service_v2 import (
        build_default_knowledge_base_direct_ppt_outline_service_v2,
    )

    return build_default_knowledge_base_direct_ppt_outline_service_v2()


def _get_ppt_entry_cards_service():
    from app.chat.application.ppt_entry_cards_service_v2 import build_default_ppt_entry_cards_service_v2

    return build_default_ppt_entry_cards_service_v2()


def _get_direct_ppt_generation_service():
    from app.chat.application.knowledge_base_direct_ppt_generation_service_v2 import (
        build_default_knowledge_base_direct_ppt_generation_service_v2,
    )

    return build_default_knowledge_base_direct_ppt_generation_service_v2()


def _with_owner(payload, current_user: dict):
    data = payload.model_dump()
    data["owner"] = current_user.get("username")
    return SimpleNamespace(**data)


def _is_report_intent_from_reply(payload: ChatReplyRequestV2) -> bool:
    question = str(payload.question or "")
    return payload.action_hint == "generate.report" or "报告" in question


@router.post("/reply", response_model=ChatResponseV2)
async def reply(payload: ChatReplyRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_reply_service().reply(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id=payload.conversation_id or "",
            trace_path="workflow" if _is_report_intent_from_reply(payload) else "fast",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


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


@router.post("/report/direct", response_model=ChatDirectReportResponseV2)
async def direct_report(payload: KnowledgeBaseDirectReportRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_direct_report_service().generate(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/ppt/outline", response_model=ChatDirectPptOutlineResponseV2)
async def direct_ppt_outline(
    payload: KnowledgeBaseDirectPptOutlineRequestV2,
    current_user: dict = Depends(get_current_user),
):
    try:
        return _get_direct_ppt_outline_service().generate_outline(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)


@router.post("/ppt/generate", response_model=ChatDirectPptGenerateResponseV2)
async def direct_ppt_generate(
    payload: KnowledgeBaseDirectPptGenerateRequestV2,
    current_user: dict = Depends(get_current_user),
):
    try:
        return _get_direct_ppt_generation_service().generate(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id="",
            trace_path="direct",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)
