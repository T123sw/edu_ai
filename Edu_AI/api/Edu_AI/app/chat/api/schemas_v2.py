from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.chat.domain.status_card import StatusCardViewModel

TracePath = Literal["fast", "workflow"]
WorkflowStatus = Literal["running", "awaiting_confirm", "completed", "interrupted", "failed"]


class ChatReplyRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    artifact_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    selected_doc_ids: List[str] = Field(default_factory=list)
    action_hint: Optional[str] = None


class ChatReportRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    selected_doc_ids: List[str] = Field(default_factory=list)
    report_config: Optional[Dict[str, Any]] = None


class TraceMetaV2(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: TracePath


class ChatResponseV2(BaseModel):
    message: Dict[str, Any]
    conversation: Dict[str, Any]
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    trace: TraceMetaV2
    status_card: Optional[StatusCardViewModel] = None


class ChatErrorResponseV2(BaseModel):
    error: Dict[str, Any]
    conversation: Dict[str, Any]
    trace: TraceMetaV2
