"""Compile teacher language into a durable, machine-checkable knowledge intent."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal, Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field


Hardness = Literal["hard", "preference"]
IntentStatus = Literal["ready_for_review", "needs_clarification"]
IntentMode = Literal["create", "supplement"]


class CourseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    language: str = "zh-CN"
    difficulty: str = ""
    duration_minutes: int | None = Field(default=None, ge=1)
    duration_lessons: int | None = Field(default=None, ge=1)
    learning_outcomes: list[str] = Field(default_factory=list)


class KnowledgeScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_topics: list[str] = Field(default_factory=list)
    exclude_topics: list[str] = Field(default_factory=list)
    preserve_existing_graph: bool = False
    preserve_existing_documents: bool = False


class DepthProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_bloom_levels: list[str] = Field(default_factory=list)
    conceptual_rigor: str = ""
    example_complexity: str = ""
    math_or_code_expectation: str = ""


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_organizations: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)
    minimum_authoritative_sources_per_topic: int = Field(default=0, ge=0, le=10)
    allow_community_fallback: bool = True
    allow_ai_fallback: bool = False
    allowed_languages: list[str] = Field(default_factory=list)
    freshness: str | None = None


class DeliverableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    type: Literal[
        "concept_explanation",
        "worked_case",
        "exercise_with_solution",
        "lab",
        "comparison",
        "glossary",
    ]
    count: int = Field(ge=1, le=100)
    hardness: Hardness = "hard"
    application: Literal["build", "topic"] = "build"
    description: str


class KnowledgeRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    kind: Literal[
        "audience",
        "duration",
        "depth",
        "scope",
        "source",
        "deliverable",
        "preservation",
    ]
    statement: str
    normalized_value: Any
    hardness: Hardness
    verification: str


class KnowledgeBuildIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = "2.0"
    mode: IntentMode
    status: IntentStatus = "ready_for_review"
    course_profile: CourseProfile
    scope: KnowledgeScope
    depth_profile: DepthProfile
    source_policy: SourcePolicy
    deliverables: list[DeliverableSpec] = Field(default_factory=list)
    requirements: list[KnowledgeRequirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list, max_length=3)
    original_text: str = Field(default="", max_length=4000)


_KNOWN_ORGANIZATIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("linux kernel", "Linux Kernel", ("docs.kernel.org",)),
    ("docker", "Docker", ("docs.docker.com",)),
    ("mit ocw", "MIT OpenCourseWare", ("ocw.mit.edu",)),
)

_GENERIC_AUTHORITY_SIGNALS: tuple[tuple[str, str], ...] = (
    (r"大学课程|高校课程|大学课件|高校课件", "大学课程"),
    (r"公认(?:的)?(?:开放)?教材|开放教材", "公认开放教材"),
    (r"官方文档|官方资料", "官方文档"),
)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_id(kind: str, value: Any) -> str:
    normalized = f"{kind}:{_clean(value).casefold()}"
    return "req_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _requirement(
    kind: str,
    statement: str,
    normalized_value: Any,
    *,
    hardness: Hardness,
    verification: str,
) -> KnowledgeRequirement:
    return KnowledgeRequirement(
        requirement_id=_stable_id(kind, normalized_value),
        kind=kind,
        statement=_clean(statement),
        normalized_value=normalized_value,
        hardness=hardness,
        verification=verification,
    )


def _domains(text: str) -> list[str]:
    domains: set[str] = set()
    for raw in re.findall(r"(?<![\w@])(?:https?://)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})(?:/[^\s，。；、]*)?", text.casefold()):
        parsed = urlsplit("https://" + raw)
        if parsed.hostname:
            domains.add(parsed.hostname.casefold())
    return sorted(domains)


def _duration(course: Mapping[str, Any], text: str) -> tuple[int | None, int | None, str]:
    combined = f"{_clean(course.get('description'))} {text}"
    match = re.search(r"(\d{1,4})\s*(分钟|小时|课时|学时)", combined)
    if not match:
        return None, None, ""
    amount, unit = int(match.group(1)), match.group(2)
    if unit == "分钟":
        return amount, None, match.group(0)
    if unit == "小时":
        return amount * 60, None, match.group(0)
    return None, amount, match.group(0)


def _quoted_topics(text: str) -> list[str]:
    topics: list[str] = []
    for match in re.finditer(
        r"(?:新增知识点|只补充|仅补充|补充|覆盖)\s*[“\"‘']([^”\"’']+)[”\"’']",
        text,
    ):
        value = _clean(match.group(1))
        if value and value not in topics:
            topics.append(value)
    return topics


def _listed_topics(text: str) -> list[str]:
    """Extract explicit scope lists that are not wrapped in quotes.

    Course creation requests are commonly generated from form fields as
    ``核心范围（...）：主题 A、主题 B``.  Treating that list as prose leaves the
    model free to accidentally satisfy it without giving the quality gate a
    durable scope contract.
    """

    topics = _quoted_topics(text)
    patterns = (
        r"核心范围(?:（[^）\n]*）|\([^\)\n]*\))?\s*[：:]\s*([^。；\n]+)",
        r"(?:必须包含的?知识点|覆盖内容)\s*[：:]\s*([^。；\n]+)",
        r"(?<!不)(?<!不要)覆盖(?!密度|程度)\s*([^。；\n]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            scope_text = re.split(
                r"[,，]\s*(?=达到|面向|适合|优先|资料|每个|要求|深度)",
                match.group(1),
                maxsplit=1,
            )[0]
            raw_items = re.split(r"[、,，]", scope_text)
            raw_items = [
                part
                for item in raw_items
                for part in (item.split("和", 1) if "和" in item else [item])
            ]
            for item in raw_items:
                value = _clean(item)
                if value and value not in topics:
                    topics.append(value)
    return topics


def _excluded_topics(text: str) -> list[str]:
    topics: list[str] = []
    for match in re.finditer(r"(?:不包含|排除|暂不涉及|不要覆盖)\s*[“\"]?([^”\"，。；\n]+)[”\"]?", text):
        value = _clean(match.group(1))
        if value and value not in topics:
            topics.append(value)
    return topics


def _prerequisites(course: Mapping[str, Any], text: str) -> list[str]:
    configured = course.get("prerequisites") or []
    if isinstance(configured, str):
        result = [_clean(item) for item in re.split(r"[、,，；;\n]", configured) if _clean(item)]
    else:
        result = [_clean(item) for item in configured if _clean(item)]
    audience = _clean(course.get("audience"))
    combined = f"{audience} {text}"
    match = re.search(r"(?:已)?(?:掌握|具备)\s*([^，。；\n]{1,80}?)(?:的[^，。；\n]{0,30}学生|基础)", combined)
    if match:
        for item in re.split(r"和|与|、|,|，", match.group(1)):
            value = _clean(item)
            if value and value not in result:
                result.append(value)
    return result


def _depth(course: Mapping[str, Any], text: str) -> DepthProfile:
    difficulty = _clean(course.get("difficulty"))
    rigor = difficulty
    for token in ("研究生", "本科基础", "高阶", "进阶", "入门", "基础"):
        if token in text:
            rigor = token
            break
    levels: list[str] = []
    if re.search(r"理解|解释|说明|辨析", text):
        levels.append("understand")
    if re.search(r"使用|配置|实现|操作|案例|练习|实验", text):
        levels.append("apply")
    if re.search(r"分析|比较|评估|排查|设计", text):
        levels.append("analyze")
    return DepthProfile(
        target_bloom_levels=levels or (["understand", "apply"] if difficulty else []),
        conceptual_rigor=rigor,
        example_complexity="可执行并可验证" if re.search(r"配置案例|实验|可运行", text) else "",
        math_or_code_expectation="包含步骤、参数解释和验证结果" if re.search(r"Docker|命令|代码|实验", text, re.I) else "",
    )


def compile_knowledge_build_intent(
    *,
    course: Mapping[str, Any],
    baseline_graph: Mapping[str, Any] | None,
    requirements: str,
) -> KnowledgeBuildIntent:
    """Produce a conservative contract without silently weakening teacher language."""

    text = str(requirements or "").strip()[:4000]
    lower = text.casefold()
    requirement_items: list[KnowledgeRequirement] = []
    assumptions: list[str] = []
    clarification: list[str] = []
    minutes, lessons, duration_statement = _duration(course, text)
    if duration_statement:
        duration_value = {"minutes": minutes, "lessons": lessons}
        requirement_items.append(_requirement(
            "duration", duration_statement, duration_value,
            hardness="hard", verification="course_time_budget",
        ))
        if lessons:
            assumptions.append("课时长度未换算为分钟，课程内容预算按课时数校验。")

    audience = _clean(course.get("audience"))
    if audience:
        requirement_items.append(_requirement(
            "audience", audience, audience,
            hardness="hard", verification="pedagogical_fit_review",
        ))

    topics = _listed_topics(text)
    excluded_topics = _excluded_topics(text)
    if topics:
        requirement_items.append(_requirement(
            "scope", "；".join(topics), topics,
            hardness="hard", verification="graph_scope_check",
        ))
    if excluded_topics:
        requirement_items.append(_requirement(
            "scope", "；".join(excluded_topics), {"exclude": excluded_topics},
            hardness="hard", verification="graph_scope_check",
        ))

    preserve_graph = bool(baseline_graph) and bool(re.search(r"保留.*(?:目录|章节)|不修改.*(?:目录|章节)", text))
    preserve_documents = bool(baseline_graph) and bool(re.search(r"保留.*(?:资料|文档)", text))
    if preserve_graph or preserve_documents:
        normalized = {"graph": preserve_graph, "documents": preserve_documents}
        requirement_items.append(_requirement(
            "preservation", "保留现有目录和资料", normalized,
            hardness="hard", verification="incremental_baseline_check",
        ))

    explicit_domains = _domains(text)
    organizations: dict[str, tuple[str, ...]] = {}
    for token, label, domains in _KNOWN_ORGANIZATIONS:
        if token in lower:
            organizations[label] = domains
    for pattern, label in _GENERIC_AUTHORITY_SIGNALS:
        if re.search(pattern, text, re.I) and not (
            label == "官方文档" and organizations
        ):
            organizations.setdefault(label, ())
    organization_domains = sorted({domain for domains in organizations.values() for domain in domains})
    all_domains = sorted(set(explicit_domains + organization_domains))
    source_is_hard = bool(re.search(r"只允许|仅使用|只能使用|必须使用|不得使用|不要.*(?:社区|博客)", text))
    source_is_preference = bool(re.search(r"优先|尽量|建议使用", text))
    required_domains = all_domains if source_is_hard else []
    preferred_domains = all_domains if source_is_preference and not source_is_hard else []
    if all_domains or organizations:
        requirement_items.append(_requirement(
            "source", text, {"domains": all_domains, "organizations": sorted(organizations)},
            hardness="hard" if source_is_hard else "preference",
            verification="source_domain_and_authority_check",
        ))
    if re.search(r"资料(?:质量)?(?:要好|好一些)|高质量资料", text) and not (all_domains or organizations):
        clarification.append("你希望优先使用哪些类型或机构的来源，例如官方文档、大学课程或指定教材？")

    deliverables: list[DeliverableSpec] = []
    per_topic_deliverables = bool(re.search(r"每个(?:主题|知识点|章节)", text))
    deliverable_patterns = (
        ("worked_case", r"(\d{1,3})\s*个[^，。；\n]{0,20}案例", "案例"),
        ("exercise_with_solution", r"(\d{1,3})\s*道[^，。；\n]{0,20}(?:练习|习题)", "带答案和解析的练习"),
        ("lab", r"(\d{1,3})\s*个[^，。；\n]{0,20}(?:实验|实训)", "实验"),
    )
    for artifact_type, pattern, label in deliverable_patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        count = int(match.group(1))
        requirement = _requirement(
            "deliverable", match.group(0), {"type": artifact_type, "count": count},
            hardness="hard", verification="learning_artifact_schema_and_count",
        )
        requirement_items.append(requirement)
        deliverables.append(DeliverableSpec(
            requirement_id=requirement.requirement_id,
            type=artifact_type,
            count=count,
            hardness="hard",
            application="topic" if per_topic_deliverables else "build",
            description=f"{count} 个{label}",
        ))

    implicit_deliverables = (
        ("concept_explanation", r"机制讲解|概念讲解|原理讲解", "机制讲解"),
        ("worked_case", r"可验证(?:例子|示例|案例)", "可验证案例"),
        ("exercise_with_solution", r"(?:练习|习题)(?![^，。；\n]{0,8}(?:答案|解析))", "带答案和解析的练习"),
        ("lab", r"实验建议|实训建议", "实验建议"),
    )
    existing_types = {item.type for item in deliverables}
    for artifact_type, pattern, label in implicit_deliverables:
        match = re.search(pattern, text)
        if not match or artifact_type in existing_types:
            continue
        application = "topic" if per_topic_deliverables else "build"
        normalized = {"type": artifact_type, "count": 1, "application": application}
        requirement = _requirement(
            "deliverable", match.group(0), normalized,
            hardness="hard", verification="learning_artifact_schema_and_count",
        )
        requirement_items.append(requirement)
        deliverables.append(DeliverableSpec(
            requirement_id=requirement.requirement_id,
            type=artifact_type,
            count=1,
            hardness="hard",
            application=application,
            description=(f"每个主题至少 1 个{label}" if application == "topic" else f"至少 1 个{label}"),
        ))
        existing_types.add(artifact_type)

    depth = _depth(course, text)
    if re.search(r"深一点|深入一些|更深入", text) and not re.search(r"研究生|本科|高阶|进阶|入门|基础|理解|应用|分析", text):
        clarification.append("你期望达到什么深度：概念理解、能够应用，还是能够分析和设计？")
    if depth.conceptual_rigor or depth.target_bloom_levels:
        requirement_items.append(_requirement(
            "depth", depth.conceptual_rigor or "、".join(depth.target_bloom_levels), depth.model_dump(),
            hardness="hard", verification="pedagogical_depth_review",
        ))

    allow_community = not bool(re.search(r"不(?:要|允许).*社区|禁止.*(?:社区|博客)", text))
    source_policy = SourcePolicy(
        preferred_organizations=(
            sorted(organizations) if source_is_preference and not source_is_hard else []
        ),
        preferred_domains=preferred_domains,
        required_domains=required_domains,
        minimum_authoritative_sources_per_topic=1 if (all_domains or organizations) else 0,
        allow_community_fallback=allow_community,
        allow_ai_fallback=bool(re.search(r"允许\s*AI|可(?:以)?\s*AI|AI\s*补充", text, re.I)),
        allowed_languages=[_clean(course.get("language")) or "zh-CN"],
    )
    prerequisites = _prerequisites(course, text)
    clarification = clarification[:3]
    return KnowledgeBuildIntent(
        mode="supplement" if baseline_graph else "create",
        status="needs_clarification" if clarification else "ready_for_review",
        course_profile=CourseProfile(
            audience=audience,
            prerequisites=prerequisites,
            language=_clean(course.get("language")) or "zh-CN",
            difficulty=_clean(course.get("difficulty")),
            duration_minutes=minutes,
            duration_lessons=lessons,
            learning_outcomes=[_clean(item) for item in course.get("objectives") or [] if _clean(item)],
        ),
        scope=KnowledgeScope(
            include_topics=topics,
            exclude_topics=excluded_topics,
            preserve_existing_graph=preserve_graph,
            preserve_existing_documents=preserve_documents,
        ),
        depth_profile=depth,
        source_policy=source_policy,
        deliverables=deliverables,
        requirements=requirement_items,
        assumptions=assumptions,
        clarification_questions=clarification,
        original_text=text,
    )
