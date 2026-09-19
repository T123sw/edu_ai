"""Research-stage artifacts: a reviewed learning path is not a ready course."""
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Contract, Identifier, PositiveVersion, PreparationRequest, ShortText, SourcePolicy


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
    source_quote: str = Field(default="", max_length=4000, description="用户要求引用原话；附件引用 source_ref 时由程序回填")
    source_ref: Identifier | None = Field(default=None, description="附件要点的服务端引用 ID，不重写原文")
    source_document_id: Identifier | None = None


class ResearchBrief(Contract):
    required_resource_types: tuple[Literal['report', 'quiz', 'classroom'], ...] = Field(default=(), max_length=3)
    learning_goal: str = Field(default="", max_length=2000)
    prior_knowledge: str = Field(default="", max_length=2000)
    desired_outcomes: tuple[ShortText, ...] = Field(default=(), max_length=12)
    depth: Literal["introductory", "intermediate", "advanced"] | None = None
    source_policy: SourcePolicy | None = None
    source_policy_quote: ShortText | None = None
    topic: ShortText
    audience: ShortText
    language: Identifier
    total_minutes: PositiveVersion
    assumptions: tuple[ShortText, ...] = Field(default=(), max_length=10, description="仅记录输入确实缺失时采用的默认值；已知目标、时长、基础不是假设。材料缺失只写 material_gaps，不得据此排除课程范围或降低目标。没有必要假设时传空数组。")
    exclusions: tuple[ShortText, ...] = Field(default=(), max_length=10, description="用户明确不学或不做的内容；不得把材料缺失写成排除项")
    material_gaps: tuple[ShortText, ...] = Field(default=(), max_length=8, description="附件不足以支持用户目标的资料缺口，交给后续研究，不降低原目标")
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


class RequirementCoverage(Contract):
    requirement_id: Identifier
    kind: Literal['knowledge', 'constraint'] = Field(default='knowledge', description='知识或实现能力用 knowledge；仅语言、时间、教学顺序等要求用 constraint，不能把实现目标改标成约束。')
    status: Literal['covered', 'partial', 'missing'] = Field(description='covered 表示证据支持完整达到原始需求；只支持概念/伪代码而原目标要求可运行程序时必须 partial。不能通过 limitations 降低目标后标 covered。')
    finding_ids: tuple[Identifier, ...] = Field(default=(), max_length=12)
    reason: ShortText

    @model_validator(mode='after')
    def supported(self):
        if self.kind == 'knowledge' and self.status == 'covered' and not self.finding_ids:
            raise ValueError('已覆盖的知识能力必须关联证据结论；语言、时间等约束使用 constraint 并说明落实方式')
        return self


class ResearchBlocker(Contract):
    reason: ShortText
    coverage: tuple[RequirementCoverage, ...] = Field(min_length=1, max_length=12)
    suggested_actions: tuple[ShortText, ...] = Field(min_length=1, max_length=5)


class ResearchSummary(Contract):
    coverage: tuple[RequirementCoverage, ...] = Field(default=(), max_length=12)
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
    upload_reads: int = 0
    source_failures: dict[str, int] = Field(default_factory=dict)
    blocker: ResearchBlocker | None = None
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
    coverage: tuple[RequirementCoverage, ...] = Field(default=(), max_length=12)
    overview: ShortText
    finding_ids: tuple[Identifier, ...] = Field(min_length=1,max_length=12)
    limitations: tuple[ShortText, ...] = Field(default=(),max_length=8)


class ReferencedFinding(Contract):
    finding_id: Identifier
    claim: ShortText
    citation_refs: tuple[Identifier,...]=Field(min_length=1,max_length=8)
