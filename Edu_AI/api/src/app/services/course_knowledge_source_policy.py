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
)
_COMPLETE_SIGNALS = ("完整", "全册", "目录", "章节", "complete", "full", "table of contents")
_AUTHORITY_SUFFIXES = (".edu", ".edu.cn", ".ac.cn", ".gov", ".org")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _terms(value: str) -> set[str]:
    normalized = _clean(value).casefold()
    result = set(re.findall(r"[a-z0-9+#.-]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    result.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in result if item}


def build_course_source_queries(
    course: Mapping[str, Any],
    *,
    content_language: str,
) -> list[SourceQueryIntent]:
    title = _clean(course.get("title"))
    audience = _clean(course.get("audience"))
    base = " ".join(item for item in (title, audience) if item)
    configured = _clean(content_language) or "zh-CN"
    queries = [
        SourceQueryIntent(
            f"{base} 完整教材 PDF filetype:pdf",
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
    ]
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
    title = _clean(course.get("title"))
    path = _clean(topic.get("graph_path"))
    leaf = _clean(topic.get("title"))
    objective = _clean(topic.get("objective"))
    base = " ".join(item for item in (title, path, leaf, objective) if item)
    configured = _clean(content_language) or "zh-CN"
    queries = [
        SourceQueryIntent(f"{base} 教程 讲义", "zh-CN", "leaf", "leaf_explanation"),
        SourceQueryIntent(f"{base} 例题 案例 课程资料", "zh-CN", "leaf", "leaf_examples"),
    ]
    if configured.casefold().startswith("zh"):
        queries.append(SourceQueryIntent(f"{base} tutorial examples", "en", "leaf", "leaf_fallback"))
    else:
        queries.append(
            SourceQueryIntent(
                f"{base} tutorial examples language:{configured}",
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
            _clean(course.get("title")),
            _clean(course.get("audience")),
            _clean((topic or {}).get("title")),
            _clean((topic or {}).get("objective")),
        )
        if item
    )
    subject_terms = _terms(subject)
    matched = sum(1 for term in subject_terms if term in haystack)
    relevance = matched / len(subject_terms) if subject_terms else 0.5
    course_title = _clean(course.get("title")).casefold()
    if course_title and course_title in haystack:
        relevance = max(relevance, 0.8)

    parsed = urlsplit(_clean(url))
    hostname = (parsed.hostname or "").casefold()
    is_pdf = parsed.path.casefold().endswith(".pdf") or " pdf" in f" {haystack}"
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
    authority = 1.0 if any(hostname.endswith(suffix) for suffix in _AUTHORITY_SUFFIXES) else 0.4
    rank_score = 1 / max(1, int(bocha_rank))
    priority = round(
        0.40 * min(1.0, relevance)
        + 0.30 * completeness
        + 0.15 * format_score
        + 0.10 * authority
        + 0.05 * rank_score,
        4,
    )
    selected = parsed.scheme.casefold() == "https" and bool(hostname) and relevance > 0
    review_status = "relevant" if selected else "rejected_irrelevant"
    reason = (
        "已通过 HTTPS 与课程相关性预筛，等待正文抓取"
        if selected
        else "来源 URL 非 HTTPS，或与课程主题没有可识别的语义重合"
    )
    return {
        "title": normalized_title,
        "url": _clean(url),
        "domain": hostname,
        "source_type": "web",
        "topic_id": _clean((topic or {}).get("topic_id")) or None,
        "language": intent.language,
        "authority_tier": "textbook_candidate" if resource_kind != "web_article" else "web_discovered",
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
            "completeness_score": round(completeness, 4),
            "priority_score": priority,
            "snippet": normalized_snippet[:1000],
            "matched_topic_ids": [],
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

