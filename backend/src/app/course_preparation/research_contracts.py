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
    source_quote: str = Field(default="", description="用户要求引用原话；附件引用 source_ref 时由程序回填")
    source_ref: Identifier | None = Field(default=None, description="附件要点的服务端引用 ID，不重写原文")
    source_document_id: Identifier | None = None


class ResearchBrief(Contract):
    node_count: int | None = Field(default=None, strict=True, ge=1,
        description='本次用户明确要求的课程节点总数；未明确则 null，不自行推断。属于交付结构约束，不是正文教学要求。')
    node_count_quote: str | None = Field(default=None,
        description='node_count 非空时逐字引用本次用户明确要求节点数量的原话。')
    required_resource_types: tuple[Literal['report', 'quiz', 'classroom'], ...] = Field(default=())
    learning_goal: str = Field(default="")
    prior_knowledge: str = Field(default="")
    desired_outcomes: tuple[ShortText, ...] = Field(default=())
    depth: Literal["introductory", "intermediate", "advanced"] | None = None
    source_policy: SourcePolicy | None = None
    source_policy_quote: ShortText | None = None
    topic: ShortText
    audience: ShortText
    language: Identifier
    total_minutes: PositiveVersion
    assumptions: tuple[ShortText, ...] = Field(default=(), description="仅记录输入确实缺失时采用的默认值；已知目标、时长、基础不是假设。材料缺失只写 material_gaps，不得据此排除课程范围或降低目标。没有必要假设时传空数组。")
    exclusions: tuple[ShortText, ...] = Field(default=(), description="用户明确不学或不做的内容；不得把材料缺失写成排除项")
    material_gaps: tuple[ShortText, ...] = Field(default=(), description="附件不足以支持用户目标的资料缺口，交给后续研究，不降低原目标")
    requirements: tuple[Requirement, ...] = Field(min_length=1,
        description='需要在教学正文讲授、练习或实际体现的内容/教学方式，例如手工追踪和先例后理。'
        '节点数量、时间、语言、资源形式、来源限制、排除项分别保存在对应专用字段，不重复作为正文覆盖要求。')


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
    snapshot_id: str | None = None
    snapshot_sha256: str | None = None
    canonical_url: str | None = None
    coverage: Literal['extracted_excerpt'] = 'extracted_excerpt'


class Citation(Contract):
    source_id: Identifier
    quote: str = Field(min_length=8)


class Finding(Contract):
    finding_id: Identifier
    claim: ShortText
    citations: tuple[Citation, ...] = Field(min_length=1)


class RequirementCoverage(Contract):
    requirement_id: Identifier
    kind: Literal['knowledge', 'constraint'] = Field(default='knowledge', description='知识或实现能力用 knowledge；仅语言、时间、教学顺序等要求用 constraint，不能把实现目标改标成约束。')
    status: Literal['covered', 'partial', 'missing'] = Field(description='covered 表示证据支持完整达到原始需求；只支持概念/伪代码而原目标要求可运行程序时必须 partial。不能通过 limitations 降低目标后标 covered。')
    finding_ids: tuple[Identifier, ...] = Field(default=())
    reason: ShortText

    @model_validator(mode='after')
    def supported(self):
        if self.kind == 'knowledge' and self.status == 'covered' and not self.finding_ids:
            raise ValueError('已覆盖的知识能力必须关联证据结论；语言、时间等约束使用 constraint 并说明落实方式')
        return self


class ResearchBlocker(Contract):
    reason: ShortText
    coverage: tuple[RequirementCoverage, ...] = Field(min_length=1)
    suggested_actions: tuple[ShortText, ...] = Field(min_length=1)


class ResearchSummary(Contract):
    coverage: tuple[RequirementCoverage, ...] = Field(default=())
    overview: ShortText
    findings: tuple[Finding, ...] = Field(min_length=1)
    unresolved_gaps: tuple[ShortText, ...] = Field(default=())
    limitations: tuple[ShortText, ...] = Field(default=())


class PathNode(Contract):
    node_key: Identifier
    title: ShortText
    objectives: tuple[ShortText, ...] = Field(min_length=1)
    prerequisite_keys: tuple[Identifier, ...] = Field()
    minutes: PositiveVersion
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)
    finding_ids: tuple[Identifier, ...] = Field(min_length=1)
    source_ids: tuple[Identifier, ...] = Field(min_length=1)
    learning_activities: tuple[ShortText, ...] = Field(min_length=1)
    self_check: ShortText


class LearningPath(Contract):
    title: ShortText
    summary: ShortText
    nodes: tuple[PathNode, ...] = Field(min_length=1)
    limitations: tuple[ShortText, ...] = Field(default=())


class PathReview(Contract):
    decision: Literal['pass', 'fail']
    issues: tuple[ShortText, ...] = Field(default=())
    checked_requirement_ids: tuple[Identifier, ...] = Field(min_length=1)
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
    query: str = Field(min_length=2)


class FetchArgs(Contract):
    candidate_id: Identifier
    offset_chars: int = Field(default=0, ge=0)


class FinalizeSummary(Contract):
    coverage: tuple[RequirementCoverage, ...] = Field(default=())
    overview: ShortText
    finding_ids: tuple[Identifier, ...] = Field(min_length=1)
    limitations: tuple[ShortText, ...] = Field(default=())


class ReferencedFinding(Contract):
    finding_id: Identifier
    claim: ShortText
    citation_refs: tuple[Identifier,...]=Field(min_length=1)


class ReadEvidenceArgs(Contract):
    source_id: Identifier | None = None
    citation_ref: Identifier | None = None
    offset_chars: int = Field(default=0, ge=0)
    limit: int = Field(default=5000, ge=1, le=5000)

    @model_validator(mode='after')
    def one_handle(self):
        if bool(self.source_id)==bool(self.citation_ref):
            raise ValueError('指定且仅指定 source_id 或 citation_ref')
        return self
