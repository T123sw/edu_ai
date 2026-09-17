"""Research-stage artifacts: a reviewed learning path is not a ready course."""
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Contract, Identifier, PositiveVersion, PreparationRequest, ShortText


class ResearchRequest(PreparationRequest):
    operation: Literal['create_course'] = 'create_course'

    @model_validator(mode='after')
    def supported_input(self):
        if self.uploads or self.source_policy.mode != 'open' or self.origin or self.learning_context:
            raise ValueError('本阶段仅支持新学习需求与开放网络研究；上传及已有课程上下文尚未接入')
        return self


class Requirement(Contract):
    requirement_id: Identifier
    text: ShortText
    source_quote: ShortText


class ResearchBrief(Contract):
    topic: ShortText
    audience: ShortText
    language: Identifier
    total_minutes: PositiveVersion
    assumptions: tuple[ShortText, ...] = Field(default=(), max_length=10)
    exclusions: tuple[ShortText, ...] = Field(default=(), max_length=10)
    requirements: tuple[Requirement, ...] = Field(min_length=1, max_length=12)


class Candidate(Contract):
    candidate_id: Identifier
    url: str
    title: str
    snippet: str


class SourceEvidence(Contract):
    source_id: Identifier
    candidate_id: Identifier
    url: str
    title: str
    content: str
    content_sha256: str
    retrieved_at: str
    offset_chars: int = 0
    total_chars: int | None = None
    next_offset: int | None = None
    coverage: Literal['extracted_excerpt'] = 'extracted_excerpt'


class Citation(Contract):
    source_id: Identifier
    quote: str = Field(min_length=8, max_length=400)


class Finding(Contract):
    finding_id: Identifier
    claim: ShortText
    citations: tuple[Citation, ...] = Field(min_length=1, max_length=8)


class ResearchSummary(Contract):
    overview: ShortText
    findings: tuple[Finding, ...] = Field(min_length=1, max_length=12)
    unresolved_gaps: tuple[ShortText, ...] = Field(default=(), max_length=8)
    limitations: tuple[ShortText, ...] = Field(default=(), max_length=8)


class PathNode(Contract):
    node_key: Identifier
    title: ShortText
    objectives: tuple[ShortText, ...] = Field(min_length=1, max_length=5)
    prerequisite_keys: tuple[Identifier, ...] = Field(max_length=12)
    minutes: PositiveVersion
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=12)
    finding_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=12)
    source_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=8)
    learning_activities: tuple[ShortText, ...] = Field(min_length=1, max_length=5)
    self_check: ShortText


class LearningPath(Contract):
    title: ShortText
    summary: ShortText
    nodes: tuple[PathNode, ...] = Field(min_length=1, max_length=12)
    limitations: tuple[ShortText, ...] = Field(default=(), max_length=10)


class PathReview(Contract):
    decision: Literal['pass', 'fail']
    issues: tuple[ShortText, ...] = Field(default=(), max_length=10)
    checked_requirement_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=12)
    repair_phase: Literal['intent', 'research', 'plan'] = 'plan'

    @model_validator(mode='after')
    def coherent_decision(self):
        if (self.decision == 'pass' and self.issues) or (self.decision == 'fail' and not self.issues):
            raise ValueError('通过时不能存在阻塞问题，失败时必须说明问题')
        return self


class ResearchState(Contract):
    phase: Literal['intent', 'research', 'plan', 'review', 'done'] = 'intent'
    brief: ResearchBrief | None = None
    candidates: tuple[Candidate, ...] = ()
    evidence: tuple[SourceEvidence, ...] = ()
    summary: ResearchSummary | None = None
    draft_findings: tuple[Finding, ...] = ()
    path: LearningPath | None = None
    review: PathReview | None = None
    calls: int = 0
    searches: int = 0
    reads: int = 0
    repairs: int = 0
    errors: int = 0
    last_error: dict | None = None
    trace: tuple[dict, ...] = ()


class SearchArgs(Contract):
    query: str = Field(min_length=2, max_length=500)


class FetchArgs(Contract):
    candidate_id: Identifier
    offset_chars: int = Field(default=0, ge=0, le=200000)


class FinalizeSummary(Contract):
    overview: ShortText
    finding_ids: tuple[Identifier, ...] = Field(min_length=1,max_length=12)
    limitations: tuple[ShortText, ...] = Field(default=(),max_length=8)


class ReferencedFinding(Contract):
    finding_id: Identifier
    claim: ShortText
    citation_refs: tuple[Identifier,...]=Field(min_length=1,max_length=8)
