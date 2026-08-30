from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryCandidate(BaseModel):
    memory_type: str
    content: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_span: str
    reason: str = ""
    profile_axis: str | None = None
    expires_at: datetime | None = None
    supersedes_axis: bool = False
    raw_provider_payload: dict[str, Any] = Field(default_factory=dict)


class CandidateExtractionResult(BaseModel):
    provider: str
    status: str
    candidates: list[MemoryCandidate] = Field(default_factory=list)
    latency_ms: int = 0
    error: str = ""


class MemoryPolicyDecision(BaseModel):
    allowed: bool
    reason: str
    candidate: MemoryCandidate


class MemoryRecordDraft(BaseModel):
    subject_user_id: str
    owner_user_id: str
    course_id: str | None = None
    conversation_id: str | None = None
    task_id: str | None = None
    memory_type: str
    fact_kind: str
    content: str
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    visibility: str = "private"
    source_type: str
    source_id: str
    source_span: str
    profile_axis: str | None = None
    expires_at: datetime | None = None
    supersedes_axis: bool = False
    embedding: list[float] | None = None
    embedding_model: str | None = None
    extractor: str = "rules"
    extractor_version: str = "1"


class MemoryRecord(BaseModel):
    memory_id: str
    subject_user_id: str
    owner_user_id: str
    course_id: str | None = None
    conversation_id: str | None = None
    memory_type: str
    fact_kind: str
    content: str
    confidence: float
    importance: float
    visibility: str
    status: str
    source_type: str
    source_id: str
    source_span: str
    profile_axis: str | None = None
    evidence_count: int = 1
    score: float = 0.0
    created_at: datetime
    updated_at: datetime


class ProfileFact(BaseModel):
    profile_fact_id: str
    subject_user_id: str
    course_id: str | None = None
    profile_axis: str
    value: str
    confidence: float
    evidence_count: int
    visibility: str
    status: str
    source_memory_ids: list[str] = Field(default_factory=list)
    last_seen_at: datetime


class AgentMemoryContext(BaseModel):
    working_memory: dict[str, Any] = Field(default_factory=dict)
    learning_facts: list[dict[str, Any]] = Field(default_factory=list)
    assessment_facts: list[dict[str, Any]] = Field(default_factory=list)
    profile_facts: list[ProfileFact] = Field(default_factory=list)
    conversation_memories: list[MemoryRecord] = Field(default_factory=list)
    retrieval_notes: list[str] = Field(default_factory=list)
    denied_scopes: list[str] = Field(default_factory=list)


class MemoryWriteResult(BaseModel):
    candidate_count: int = 0
    accepted_count: int = 0
    written_count: int = 0
    rejected_count: int = 0
    shadow_candidate_count: int = 0
    provider: str = "rules"
    provider_status: str = "ok"
    memory_ids: list[str] = Field(default_factory=list)
    decisions: list[MemoryPolicyDecision] = Field(default_factory=list)


class MemoryEvalReport(BaseModel):
    case_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    false_write_rate: float
    protected_fact_rejection_rate: float


class RetrievalEvalReport(BaseModel):
    case_count: int
    recall_at_1: float
    recall_at_3: float
    mean_reciprocal_rank: float
    isolation_violation_rate: float
