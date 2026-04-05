from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from app.chat.domain.status_card import StatusCardViewModel


IntentCategory = Literal["chat", "generate_content", "research"]


class ChatRequest(BaseModel):
    """对话请求体（含意图识别入口）。"""

    question: str = Field(..., min_length=1, description="用户输入")
    conversation_id: Optional[str] = Field(default=None, description="会话ID")
    model_id: Optional[str] = Field(default=None, description="模型ID，默认使用 DEFAULT_LLM_MODEL_ID")
    owner: Optional[str] = Field(default=None, description="当前用户名")
    artifact_id: Optional[str] = Field(default=None, description="当前活跃产物ID")
    use_rag: Optional[bool] = Field(default=None, description="是否启用知识库检索，若为空由系统判断")
    allow_rag: bool = Field(default=False, description="是否允许使用 RAG")
    allow_web: bool = Field(default=False, description="是否允许使用 Web")
    action_hint: Optional[str] = Field(default=None, description="前端显式动作提示")
    selected_doc_ids: List[str] = Field(default_factory=list, description="指定检索的文档ID列表")
    course_id: Optional[str] = Field(default=None, description="课程ID（用于课程知识库关联）")


class ChatResponse(BaseModel):
    """对话响应体。"""

    answer: str
    conversation_id: str
    model_id: str
    intent_category: IntentCategory
    title: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChatResponseV2(BaseModel):
    message: Dict[str, Any]
    conversation: Dict[str, Any]
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status_card: Optional[StatusCardViewModel] = None


class SkillHealthCheckRequest(BaseModel):
    meta: Dict[str, Any] = Field(default_factory=dict, description="chat接口返回的meta对象")


class SkillHealthCheckResponse(BaseModel):
    score: float
    grade: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
