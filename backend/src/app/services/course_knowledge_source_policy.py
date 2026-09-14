"""Query and ranking policy for textbook-first course knowledge discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence
from urllib.parse import urlsplit


DiscoveryScope = Literal["course", "leaf"]
DiscoveryIntent = Literal[
    "complete_textbook_pdf",
    "complete_textbook_html",
    "course_notes_pdf",
    "leaf_explanation",
    "leaf_examples",
    "leaf_fallback",
]


@dataclass(frozen=True)
class SourceQueryIntent:
    query: str
    language: str
    discovery_scope: DiscoveryScope
    intent: DiscoveryIntent


_TEXTBOOK_SIGNALS = (
    "教材",
    "教科书",
    "讲义",
    "课程笔记",
    "章节",
    "目录",
    "textbook",
    "course notes",
    "lecture notes",
    "open course",
    "book",
)
_COMPLETE_SIGNALS = ("完整", "全册", "目录", "章节", "complete", "full", "table of contents")
_AUTHORITY_SUFFIXES = (".edu", ".edu.cn", ".ac.cn", ".gov", ".gov.cn")
_KNOWN_AUTHORITATIVE_DOMAINS = (
    "docs.kernel.org",
    "docs.python.org",
    "docs.docker.com",
    "developer.mozilla.org",
    "kubernetes.io",
    "learn.microsoft.com",
    "openstax.org",
    "postgresql.org",
    "rfc-editor.org",
    "w3.org",
)
_LOW_QUALITY_DOMAIN_FRAGMENTS = (
    "book118.",
    "doc88.",
    "docin.",
    "360docs.",
    "doc.guandang.",
    "download.csdn.",
    "jinchutou.",
    "kaoyan.",
    "www.jd.",
    "renrendoc.",
    "taodocs.",
    "wenku.baidu.",
    "wenku.csdn.",
    "wendang.",
    "wendoc.",
    "yuanchuangyundoc.",
)
_LOW_QUALITY_BRAND_SIGNALS = ("原创力文档", "豆丁网", "道客巴巴", "人人文库")
_NON_INSTRUCTIONAL_TITLE_SIGNALS = (
    "教学大纲",
    "考试大纲",
    "课程简介",
    "教学日历",
    "课程设计题目",
    "本科教务",
    "课程教学",
    "目录书摘",
    "[PDF] 目录",
    "【PDF】目录",
    "讲课比赛",
    "教学比赛",
    "成功举办",
    "新闻通知",
    "通知公告",
    "招生简章",
    "人才培养方案",
    "会议纪要",
    "获奖名单",
    "prior releases",
    "release notes",
    "changelog",
    "version archive",
    "版本发布说明",
    "历史版本归档",
)
_DOMAIN_QUERY_HINTS = {
    "docs.kernel.org": "cgroup v2 cpu.max memory.max io.max",
    "docs.docker.com": "container resource constraints --cpus --memory block IO",
}
_GENERIC_QUERY_TERMS = {
    "official",
    "documentation",
    "guide",
    "site",
    "教程",
    "讲义",
    "课程资料",
}


def _course_aliases(title: str) -> list[str]:
    normalized = _clean(title).casefold()
    aliases: list[str] = []
    if "操作系统" in normalized:
        aliases.extend(["operating system", "operating systems", "xv6", "ostep"])
    return aliases


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _retrieval_course_title(value: Any) -> str:
    title = _clean(value)
    return _clean(
        re.sub(
            r"[（(][^）)\n]*(?:e2e|测试|验收)[^）)\n]*[）)]",
            "",
            title,
            flags=re.IGNORECASE,
        )
    )


def _terms(value: str) -> set[str]:
    normalized = _clean(value).casefold()
    result = set(re.findall(r"[a-z0-9+#.-]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    result.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in result if item}


def _query_focus_score(query: str, title: str, snippet: str, url: str) -> float:
    """Prefer a page about the requested controller over a broad same-domain page."""

    without_site = re.sub(r"\bsite:\S+", " ", _clean(query), flags=re.IGNORECASE)
    query_terms = {
        item
        for item in _terms(without_site)
        if item not in _GENERIC_QUERY_TERMS and len(item) >= 2
    }
    if not query_terms:
        return 0.5
    haystack = f"{_clean(title)} {_clean(snippet)} {_clean(url)}".casefold()
    matched = sum(1 for term in query_terms if term in haystack)
    return round(matched / len(query_terms), 4)


def _query_title_focus_score(query: str, title: str, url: str) -> float:
    """Demand a visible page-level match, not only an incidental snippet mention."""

    return _query_focus_score(query, title, "", url)


def _domain_matches(hostname: str, domains: Sequence[str]) -> bool:
    normalized = hostname.casefold().strip(".")
    return any(
        normalized == domain.casefold().strip(".")
        or normalized.endswith("." + domain.casefold().strip("."))
        for domain in domains
        if _clean(domain)
    )


def is_authoritative_source_domain(hostname: str) -> bool:
    """Return whether a domain has an independently recognizable authority signal."""

    normalized = _clean(hostname).casefold().strip(".")
    if not normalized:
        return False
    return (
        any(normalized.endswith(suffix) for suffix in _AUTHORITY_SUFFIXES)
        or any(
            normalized == domain or normalized.endswith("." + domain)
            for domain in _KNOWN_AUTHORITATIVE_DOMAINS
        )
        or normalized.startswith(("docs.", "developer."))
    )


def is_low_quality_source(hostname: str, title: str = "", snippet: str = "") -> bool:
    """Reject known document mirrors/marketplaces before downloading their pages."""

    normalized = _clean(hostname).casefold()
    haystack = f"{_clean(title)} {_clean(snippet)}"
    return any(token in normalized for token in _LOW_QUALITY_DOMAIN_FRAGMENTS) or any(
        signal in haystack for signal in _LOW_QUALITY_BRAND_SIGNALS
    )


def is_non_instructional_source_title(title: str) -> bool:
    normalized = _clean(title).casefold()
    return any(signal.casefold() in normalized for signal in _NON_INSTRUCTIONAL_TITLE_SIGNALS)


def _requested_material_terms(topic: Mapping[str, Any]) -> str:
    requested = topic.get("requested_materials")
    if isinstance(requested, Sequence) and not isinstance(requested, (str, bytes)):
        requested_text = " ".join(_clean(item) for item in requested if _clean(item))
    else:
        requested_text = _clean(requested)
    artifact_labels = {
        "concept_explanation": "概念讲解",
        "worked_case": "完整案例 步骤 验证",
        "exercise_with_solution": "例题 练习 答案 解析",
        "lab": "实验 步骤 结果验证",
        "comparison": "对比分析",
        "glossary": "术语表",
    }
    deliverable_terms = [
        artifact_labels.get(_clean(item.get("type")), _clean(item.get("type")))
        for item in topic.get("deliverables") or []
        if isinstance(item, Mapping)
    ]
    return " ".join(item for item in (requested_text, *deliverable_terms) if item)


def build_course_source_queries(
    course: Mapping[str, Any],
    *,
    content_language: str,
) -> list[SourceQueryIntent]:
    title = _retrieval_course_title(course.get("title"))
    audience = _clean(course.get("audience"))
    base = " ".join(item for item in (title, audience) if item)
    configured = _clean(content_language) or "zh-CN"
    academic_domain = "edu.cn" if configured.casefold().startswith("zh") else "edu"
    queries: list[SourceQueryIntent] = []
    if "操作系统" in title or "operating system" in title.casefold():
        queries.extend(
            [
                SourceQueryIntent(
                    "site:pdos.csail.mit.edu xv6 teaching operating system book PDF",
                    "en",
                    "course",
                    "complete_textbook_pdf",
                ),
                SourceQueryIntent(
                    "site:pages.cs.wisc.edu OSTEP Operating Systems Three Easy Pieces book",
                    "en",
                    "course",
                    "complete_textbook_html",
                ),
                SourceQueryIntent(
                    "site:cs.nju.edu.cn 操作系统 课程 讲义",
                    "zh-CN",
                    "course",
                    "complete_textbook_html",
                ),
            ]
        )
    queries.extend([
        SourceQueryIntent(
            f"site:{academic_domain} {base} 完整教材 课程讲义 PDF filetype:pdf",
            "zh-CN",
            "course",
            "complete_textbook_pdf",
        ),
        SourceQueryIntent(
            f"{base} 课程讲义 教材 章节 目录 PDF",
            "zh-CN",
            "course",
            "course_notes_pdf",
        ),
        SourceQueryIntent(
            f"{base} 开放教材 完整教程 章节 目录",
            "zh-CN",
            "course",
            "complete_textbook_html",
        ),
    ])
    if configured.casefold().startswith("zh"):
        queries.extend(
            [
                SourceQueryIntent(
                    f"{title} open textbook complete course PDF",
                    "en",
                    "course",
                    "complete_textbook_pdf",
                ),
                SourceQueryIntent(
                    f"{title} course notes lecture notes",
                    "en",
                    "course",
                    "complete_textbook_html",
                ),
            ]
        )
    else:
        queries.append(
            SourceQueryIntent(
                f"{title} open textbook course notes language:{configured}",
                configured,
                "course",
                "complete_textbook_html",
            )
        )
    return queries


def build_leaf_source_queries(
    course: Mapping[str, Any],
    topic: Mapping[str, Any],
    *,
    content_language: str,
) -> list[SourceQueryIntent]:
    title = _retrieval_course_title(course.get("title"))
    audience = _clean(topic.get("audience")) or _clean(course.get("audience"))
    path = _clean(topic.get("graph_path"))
    leaf = _clean(topic.get("title"))
    objective = _clean(topic.get("objective"))
    depth = dict(topic.get("depth_profile") or {})
    depth_terms = " ".join(
        item
        for item in (
            _clean(depth.get("conceptual_rigor")),
            _clean(depth.get("example_complexity")),
            _clean(depth.get("math_or_code_expectation")),
        )
        if item
    )
    subject_base = " ".join(item for item in (title, leaf, objective) if item)
    teaching_base = " ".join(
        item for item in (title, audience, path, leaf, objective, depth_terms) if item
    )
    policy = dict(topic.get("source_policy") or {})
    required_domains = [_clean(item) for item in policy.get("required_domains") or [] if _clean(item)]
    preferred_domains = [_clean(item) for item in policy.get("preferred_domains") or [] if _clean(item)]
    domains = required_domains or preferred_domains
    requested_terms = _requested_material_terms(topic)
    configured = _clean(content_language) or "zh-CN"
    if domains:
        queries = [
            SourceQueryIntent(
                " ".join(
                    item
                    for item in (
                        f"site:{domain}",
                        _DOMAIN_QUERY_HINTS.get(domain.casefold(), subject_base),
                        "official documentation guide",
                    )
                    if item
                ),
                "en",
                "leaf",
                "leaf_examples" if requested_terms else "leaf_explanation",
            )
            for domain in domains
        ]
        fallback_query = " ".join(
            item
            for item in (teaching_base, requested_terms, "教程 讲义 例题 案例 课程资料")
            if item
        )
        if bool(policy.get("allow_community_fallback", True)):
            queries.append(
                SourceQueryIntent(
                    fallback_query,
                    "zh-CN" if configured.casefold().startswith("zh") else configured,
                    "leaf",
                    "leaf_fallback",
                )
            )
        return queries

    academic_domain = "edu.cn" if configured.casefold().startswith("zh") else "edu"
    queries = [
        SourceQueryIntent(
            f"site:{academic_domain} {title} {leaf} 教程 课程讲义",
            "zh-CN",
            "leaf",
            "leaf_explanation",
        ),
        SourceQueryIntent(
            " ".join(
                item
                for item in (
                    f"site:{academic_domain}",
                    title,
                    leaf,
                    requested_terms,
                    "课件 PDF 例题 案例",
                )
                if item
            ),
            "zh-CN",
            "leaf",
            "leaf_examples",
        ),
        SourceQueryIntent(
            " ".join(
                item
                for item in (teaching_base, requested_terms, "教程 例题 案例 课程资料")
                if item
            ),
            "zh-CN" if configured.casefold().startswith("zh") else configured,
            "leaf",
            "leaf_fallback",
        ),
    ]
    if configured.casefold().startswith("zh"):
        queries.append(
            SourceQueryIntent(
                f"{teaching_base} tutorial examples",
                "en",
                "leaf",
                "leaf_fallback",
            )
        )
    else:
        queries.append(
            SourceQueryIntent(
                " ".join(
                    item
                    for item in (
                        teaching_base,
                        f"tutorial examples language:{configured}",
                    )
                    if item
                ),
                configured,
                "leaf",
                "leaf_fallback",
            )
        )
    return queries


def classify_source_candidate(
    *,
    intent: SourceQueryIntent,
    course: Mapping[str, Any],
    title: str,
    snippet: str,
    url: str,
    bocha_rank: int,
    topic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_title = _clean(title) or _clean(url)
    normalized_snippet = _clean(snippet)
    haystack = f"{normalized_title} {normalized_snippet} {_clean(url)}".casefold()
    subject = " ".join(
        item
        for item in (
            _retrieval_course_title(course.get("title")),
            _clean(course.get("audience")),
            _clean((topic or {}).get("title")),
            _clean((topic or {}).get("objective")),
        )
        if item
    )
    subject = " ".join((subject, *_course_aliases(str(course.get("title") or ""))))
    subject_terms = _terms(subject)
    matched = sum(1 for term in subject_terms if term in haystack)
    relevance = matched / len(subject_terms) if subject_terms else 0.5
    topic_text = " ".join(
        item
        for item in (
            _clean((topic or {}).get("title")),
            _clean((topic or {}).get("objective")),
        )
        if item
    )
    topic_terms = _terms(topic_text)
    topic_matched = sum(1 for term in topic_terms if term in haystack)
    topic_relevance = topic_matched / len(topic_terms) if topic_terms else 1.0
    course_title = _retrieval_course_title(course.get("title")).casefold()
    if not topic and (
        (course_title and course_title in haystack)
        or any(alias in haystack for alias in _course_aliases(course_title))
    ):
        relevance = max(relevance, 0.8)

    parsed = urlsplit(_clean(url))
    hostname = (parsed.hostname or "").casefold()
    source_policy = dict((topic or {}).get("source_policy") or {})
    required_domains = [
        _clean(item).casefold()
        for item in source_policy.get("required_domains") or []
        if _clean(item)
    ]
    preferred_domains = [
        _clean(item).casefold()
        for item in source_policy.get("preferred_domains") or []
        if _clean(item)
    ]
    required_match = _domain_matches(hostname, required_domains) if required_domains else None
    preferred_match = _domain_matches(hostname, preferred_domains) if preferred_domains else None
    is_pdf = parsed.path.casefold().endswith(".pdf") or "[pdf]" in normalized_title.casefold()
    textbook_matches = sum(signal in haystack for signal in _TEXTBOOK_SIGNALS)
    completeness_matches = sum(signal in haystack for signal in _COMPLETE_SIGNALS)
    if textbook_matches:
        resource_kind = "textbook" if completeness_matches or is_pdf else "course_notes"
    elif "讲义" in haystack or "notes" in haystack:
        resource_kind = "course_notes"
    else:
        resource_kind = "web_article"
    completeness = min(1.0, textbook_matches * 0.25 + completeness_matches * 0.2)
    format_score = 1.0 if is_pdf else (0.7 if resource_kind in {"textbook", "course_notes"} else 0.3)
    policy_domain_match = bool(required_match or preferred_match)
    institutional_authority = is_authoritative_source_domain(hostname)
    low_quality_source = is_low_quality_source(hostname, normalized_title, normalized_snippet)
    non_instructional = is_non_instructional_source_title(normalized_title)
    authority = 1.0 if policy_domain_match or institutional_authority else 0.4
    rank_score = 1 / max(1, int(bocha_rank))
    query_focus = _query_focus_score(
        intent.query, normalized_title, normalized_snippet, _clean(url)
    )
    query_title_focus = _query_title_focus_score(
        intent.query, normalized_title, _clean(url)
    )
    priority = round(
        0.30 * min(1.0, relevance)
        + 0.25 * query_focus
        + 0.20 * completeness
        + 0.10 * format_score
        + 0.10 * authority
        + 0.05 * rank_score,
        4,
    )
    selected = (
        parsed.scheme.casefold() == "https"
        and bool(hostname)
        and relevance > 0
        and topic_relevance > 0
        and not low_quality_source
        and not non_instructional
        and required_match is not False
        and not (
            preferred_match is False
            and "site:" in intent.query.casefold()
        )
        and not (
            topic
            and policy_domain_match
            and "site:" in intent.query.casefold()
            and query_title_focus <= 0
        )
    )
    review_status = "relevant" if selected else "rejected_irrelevant"
    if non_instructional:
        reason = "来源是课程简介或教学大纲，不足以作为知识点正文"
    elif low_quality_source:
        reason = "来源属于低质量文档镜像或下载站，已在抓取前拒绝"
    elif required_match is False:
        reason = "来源不在教师限定的必选域名内"
    elif preferred_match is False and "site:" in intent.query.casefold():
        reason = "优先来源检索阶段不接收搜索服务返回的站外结果"
    elif (
        topic
        and policy_domain_match
        and "site:" in intent.query.casefold()
        and query_title_focus <= 0
    ):
        reason = "页面标题与路径未命中本轮检索主题，仅摘要偶然提及，已拒绝"
    elif selected and policy_domain_match:
        reason = "已匹配教师指定来源，并通过 HTTPS 与课程相关性预筛"
    elif selected:
        reason = "已通过 HTTPS 与课程相关性预筛，等待正文抓取"
    else:
        reason = "来源 URL 非 HTTPS，或与课程主题没有可识别的语义重合"
    return {
        "title": normalized_title,
        "url": _clean(url),
        "domain": hostname,
        "source_type": "web",
        "topic_id": _clean((topic or {}).get("topic_id")) or None,
        "language": intent.language,
        "authority_tier": (
            "teacher_required_source"
            if required_match
            else "teacher_preferred_source"
            if preferred_match
            else "authoritative_source"
            if institutional_authority
            else "textbook_candidate"
            if resource_kind != "web_article"
            else "web_discovered"
        ),
        "review_status": review_status,
        "review_reason": reason,
        "selected": selected,
        "relevance_score": round(relevance, 4),
        "metadata": {
            "query": intent.query,
            "discovery_scope": intent.discovery_scope,
            "discovery_intent": intent.intent,
            "resource_kind": resource_kind,
            "content_format_hint": "pdf" if is_pdf else "html",
            "bocha_rank": int(bocha_rank),
            "course_relevance": round(relevance, 4),
            "topic_relevance": round(topic_relevance, 4),
            "topic_title": _clean((topic or {}).get("title")),
            "topic_objective": _clean((topic or {}).get("objective")),
            "completeness_score": round(completeness, 4),
            "priority_score": priority,
            "query_focus_score": query_focus,
            "query_title_focus_score": query_title_focus,
            "snippet": normalized_snippet[:1000],
            "matched_topic_ids": [],
            "required_domain_match": required_match,
            "preferred_domain_match": preferred_match,
            "institutional_authority": institutional_authority,
            "low_quality_source": low_quality_source,
            "non_instructional": non_instructional,
            "requirement_ids": list((topic or {}).get("requirement_ids") or []),
        },
    }


def rank_source_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(item) for item in candidates),
        key=lambda item: (
            not bool(item.get("selected")),
            -float((item.get("metadata") or {}).get("priority_score") or 0),
            int((item.get("metadata") or {}).get("bocha_rank") or 10_000),
            str(item.get("url") or ""),
        ),
    )
