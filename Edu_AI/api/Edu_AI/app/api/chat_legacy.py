"""Legacy chat / conversation / models routes — compat layer.

Thin HTTP wrappers delegating to app.services.chat_service.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ModelInfo
from app.services.chat_service import chat as chat_service
from core import Config, conversation_storage

router = APIRouter(tags=["chat-legacy"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        username = current_user.get("username")
        result = chat_service(
            question=request.question,
            conversation_id=request.conversation_id,
            top_k=request.top_k,
            model_id=request.model_id,
            use_rag=request.use_rag if request.use_rag is not None else True,
            selected_doc_ids=request.selected_doc_ids,
            owner=username,
        )
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {exc}") from exc


@router.get("/conversations/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    try:
        return conversation_storage.get_conversation(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="对话不存在") from exc


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conversation_storage.delete_conversation(conversation_id)
    return {"message": "对话历史已删除"}


@router.post("/conversations/{conversation_id}/truncate")
async def truncate_conversation(conversation_id: str, keep_count: int):
    try:
        conversation_storage.truncate_messages(conversation_id, keep_count)
        return {"message": f"对话已截断，保留前 {keep_count} 条消息"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"截断对话失败: {exc}") from exc


@router.delete("/conversations/{conversation_id}/messages/{message_index}")
async def delete_message_pair(conversation_id: str, message_index: int):
    try:
        conversation_storage.delete_message_pair(conversation_id, message_index)
        return {"message": "消息已删除"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除消息失败: {exc}") from exc


@router.get("/conversations")
async def list_conversations():
    return conversation_storage.list_conversations()


@router.get("/models", response_model=List[ModelInfo])
async def list_models():
    return Config.get_public_llm_models()
