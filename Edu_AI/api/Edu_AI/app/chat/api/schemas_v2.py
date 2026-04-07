from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.chat.domain.artifact_reference import ArtifactReferencePayload
from app.chat.domain.conversation_reference import ConversationReferencePayload
from app.chat.domain.status_card import StatusCardViewModel

TracePath = Literal["fast", "workflow"]
DirectTracePath = Literal["direct"]
WorkflowStatus = Literal["running", "awaiting_confirm", "completed", "interrupted", "failed"]
ReportEntryMode = Literal["knowledge_base_report", "chat_report"]
ReportEntryCardType = Literal["preset", "recommended"]
PresetKey = Literal["brief", "detailed", "study_plan", "custom"]
RecommendationType = Literal[
    "summary",
    "comparison",
    "risk_analysis",
    "teaching_suggestion",
    "study_focus",
    "theme_outline",
]
FitScore = Literal["high", "medium", "low"]


class ChatReplyRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact_reference: Optional[ArtifactReferencePayload] = None
    conversation_reference: Optional[ConversationReferencePayload] = None
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
    entry_mode: Optional[ReportEntryMode] = None
    prompt_draft: Optional[str] = None
    final_user_prompt: Optional[str] = None
    selected_card: Optional["ReportEntryCardSelectionV2"] = None


class ChatReportCardsRequestV2(BaseModel):
    course_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)


class KnowledgeBaseDirectReportRequestV2(BaseModel):
    question: str
    course_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)
    report_config: Optional[Dict[str, Any]] = None
    prompt_draft: Optional[str] = None
    final_user_prompt: Optional[str] = None
    selected_card: Optional["ReportEntryCardSelectionV2"] = None


class ReportEntryCardSelectionV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    preset_key: Optional[PresetKey] = None
    recommendation_type: Optional[RecommendationType] = None


class ReportEntryCardV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    title: str
    description: str
    prompt_draft: str
    preset_key: Optional[PresetKey] = None
    recommendation_type: Optional[RecommendationType] = None
    recommendation_source: Optional[Literal["doc_summaries"]] = None
    fit_score: Optional[FitScore] = None


class ChatReportCardsResponseV2(BaseModel):
    entry_mode: ReportEntryMode
    cards: List[ReportEntryCardV2] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)


class TraceMetaV2(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: TracePath


class DirectTraceMetaV2(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: DirectTracePath


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


class ChatDirectReportResponseV2(BaseModel):
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2
