from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.chat.domain.status_card import StatusCardViewModel


IntentCategory = Literal["chat", "generate_content", "research"]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="user question")
    conversation_id: Optional[str] = Field(default=None, description="conversation id")
    model_id: Optional[str] = Field(default=None, description="model id")
    owner: Optional[str] = Field(default=None, description="owner")
    artifact_id: Optional[str] = Field(default=None, description="artifact id")
    use_rag: Optional[bool] = Field(default=None, description="legacy rag flag")
    allow_rag: bool = Field(default=False, description="allow rag retrieval")
    allow_web: bool = Field(default=False, description="allow web retrieval")
    action_hint: Optional[str] = Field(default=None, description="action hint")
    selected_doc_ids: List[str] = Field(default_factory=list, description="selected document ids")
    course_id: Optional[str] = Field(default=None, description="course id")
    scope_type: str = Field(default="course", description="workspace scope type")
    scope_id: Optional[str] = Field(default=None, description="workspace scope identifier")


class ChatResponse(BaseModel):
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
    meta: Dict[str, Any] = Field(default_factory=dict, description="chat metadata")


class SkillHealthCheckResponse(BaseModel):
    score: float
    grade: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
