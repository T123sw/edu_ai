"""Per-leaf web source discovery for a confirmed course knowledge graph."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.course_knowledge_source_policy import (
    build_course_source_queries,
    build_leaf_source_queries,
    classify_source_candidate,
    rank_source_candidates,
)


SearchProvider = Callable[[str, int], Sequence[Any]]
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_id(value: str) -> str:
    return f"source-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def canonical_source_url(value: Any) -> str:
    raw = _clean(value)
    parsed = urlsplit(raw)
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    if scheme != "https" or not hostname:
        return ""
    port = parsed.port
    netloc = hostname if not port or port == 443 else f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in _TRACKING_KEYS
        ),
        doseq=True,
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def confirmed_graph_topics(graph: Mapping[str, Any]) -> list[dict[str, str]]:
    topics: list[dict[str, str]] = []

    def visit(node: Mapping[str, Any], path: list[str]) -> None:
        label = _clean(node.get("label"))
        next_path = [*path, label] if label else list(path)
        children = [item for item in node.get("children") or [] if isinstance(item, Mapping)]
        if not children:
            data = dict(node.get("data") or {})
            topic_id = _clean(node.get("id"))
            if topic_id:
                topics.append(
                    {
                        "topic_id": topic_id,
                        "title": label,
                        "objective": _clean(data.get("summary")),
                        "graph_path": " / ".join(next_path),
                    }
                )
            return
        for child in children:
            visit(child, next_path)

    visit(graph, [])
    return topics


def _semantic_terms(topic: Mapping[str, Any]) -> set[str]:
    text = f"{_clean(topic.get('title'))} {_clean(topic.get('objective'))}".casefold()
    terms = {item for item in re.findall(r"[a-z0-9+#.-]{2,}", text) if len(item) >= 2}
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    terms.update(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    title = _clean(topic.get("title")).casefold()
    if title:
        terms.add(title)
    return {item for item in terms if item}


def _relevance(topic: Mapping[str, Any], title: str, snippet: str) -> float:
    haystack = f"{title} {snippet}".casefold()
    terms = _semantic_terms(topic)
    if not terms:
        return 0.5
    matched = sum(1 for term in terms if term in haystack)
    return round(matched / len(terms), 4)


def _hit_value(hit: Any, key: str) -> Any:
    if isinstance(hit, Mapping):
        return hit.get(key)
    return getattr(hit, key, None)


def _queries(
    *,
    course: Mapping[str, Any],
    topic: Mapping[str, Any],
    content_language: str,
) -> list[tuple[str, str]]:
    course_title = _clean(course.get("title"))
    audience = _clean(course.get("audience"))
    path = _clean(topic.get("graph_path"))
    title = _clean(topic.get("title"))
    objective = _clean(topic.get("objective"))
    base = " ".join(item for item in (course_title, path, title, objective, audience) if item)
    chinese = f"{base} 教学 课程资料 中文"
    configured = _clean(content_language) or "zh-CN"
    if configured.casefold().startswith("zh"):
        supplemental = f"{base} tutorial educational resource English"
        supplemental_language = "en"
    else:
        supplemental = f"{base} tutorial educational resource language:{configured}"
        supplemental_language = configured
    return [(chinese, "zh-CN"), (supplemental, supplemental_language)]


def discover_course_textbook_sources(
    build: Mapping[str, Any],
    *,
    search_provider: SearchProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Discover course-wide textbook candidates before leaf gap search."""

    config = dict(build.get("config") or {})
    max_textbooks = max(0, min(5, int(config.get("max_online_textbooks", 2))))
    if max_textbooks == 0:
        return {
            "source_candidates": [],
            "warnings": [],
            "metrics": {"candidate_count": 0, "selected_textbook_count": 0, "search_failure_count": 0},
        }
    course = dict(build.get("course_snapshot") or {})
    provider = search_provider
    if provider is None:
        from app.services.deepsearch_service import search_web_sources

        provider = search_web_sources
    timestamp = (now or (lambda: datetime.now(timezone.utc)))().isoformat()
    recall_limit = max(6, max_textbooks * 3)
    candidates_by_url: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []

    for intent in build_course_source_queries(
        course,
        content_language=str(config.get("content_language") or "zh-CN"),
    ):
        try:
            hits = provider(intent.query, recall_limit)
        except Exception as exc:
            warnings.append(
                {
                    "code": "SOURCE_SEARCH_FAILED",
                    "topic_id": "",
                    "query": intent.query,
                    "message": str(exc),
                }
            )
            continue
        for rank, hit in enumerate(list(hits or []), start=1):
            original_url = _clean(_hit_value(hit, "url"))
            canonical_url = canonical_source_url(original_url)
            candidate = classify_source_candidate(
                intent=intent,
                course=course,
                title=_clean(_hit_value(hit, "title")) or original_url,
                snippet=_clean(_hit_value(hit, "content")),
                url=canonical_url or original_url,
                bocha_rank=rank,
            )
            resource_kind = str((candidate.get("metadata") or {}).get("resource_kind") or "")
            if resource_kind not in {"textbook", "course_notes"}:
                candidate["selected"] = False
                candidate["review_status"] = "rejected_irrelevant"
                candidate["review_reason"] = "课程级教材发现只保留完整教材或课程讲义"
            candidate.update(
                {
                    "candidate_id": _stable_id(f"course:{canonical_url or original_url}"),
                    "topic_id": None,
                    "license_name": None,
                    "license_url": None,
                }
            )
            candidate["metadata"] = {
                **dict(candidate.get("metadata") or {}),
                "provider": "configured_web_search",
                "discovered_at": timestamp,
                "original_url": original_url,
                "canonical_url": canonical_url,
            }
            dedupe_url = canonical_url or original_url
            existing = candidates_by_url.get(dedupe_url)
            if existing is None or float(candidate["metadata"]["priority_score"]) > float(
                (existing.get("metadata") or {}).get("priority_score") or 0
            ):
                candidates_by_url[dedupe_url] = candidate
        ranked = rank_source_candidates(list(candidates_by_url.values()))
        if sum(bool(item.get("selected")) for item in ranked) >= max_textbooks:
            break

    ranked = rank_source_candidates(list(candidates_by_url.values()))
    selected_seen = 0
    for candidate in ranked:
        if not candidate.get("selected"):
            continue
        selected_seen += 1
        if selected_seen > max_textbooks:
            candidate["selected"] = False
            candidate["review_status"] = "rejected_irrelevant"
            candidate["review_reason"] = "已达到在线教材候选上限"
    return {
        "source_candidates": ranked,
        "warnings": warnings,
        "metrics": {
            "candidate_count": len(ranked),
            "selected_textbook_count": min(selected_seen, max_textbooks),
            "search_failure_count": len(warnings),
        },
    }


def discover_course_knowledge_sources(
    build: Mapping[str, Any],
    *,
    search_provider: SearchProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    graph = dict(build.get("graph_draft") or {})
    topics = confirmed_graph_topics(graph)
    if not topics:
        raise ValueError("已确认知识图谱没有叶级知识点")
    config = dict(build.get("config") or {})
    max_results = max(1, int(config.get("max_search_results_per_leaf") or 6))
    course = dict(build.get("course_snapshot") or {})
    timestamp = (now or (lambda: datetime.now(timezone.utc)))().isoformat()
    provider = search_provider
    if provider is None:
        from app.services.deepsearch_service import search_web_sources

        provider = search_web_sources

    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    candidate_index_by_url: dict[str, int] = {}
    queries_by_topic: dict[str, list[str]] = {}

    for topic in topics:
        topic_id = topic["topic_id"]
        queries = _queries(
            course=course,
            topic=topic,
            content_language=str(config.get("content_language") or "zh-CN"),
        )
        queries_by_topic[topic_id] = [query for query, _language in queries]
        relevant_count = 0
        for query, query_language in queries:
            if relevant_count >= max_results:
                break
            try:
                hits = provider(query, max_results)
            except Exception as exc:
                warnings.append(
                    {
                        "code": "SOURCE_SEARCH_FAILED",
                        "topic_id": topic_id,
                        "query": query,
                        "message": str(exc),
                    }
                )
                continue
            for hit in list(hits or []):
                original_url = _clean(_hit_value(hit, "url"))
                canonical_url = canonical_source_url(original_url)
                dedupe_url = canonical_url or original_url
                title = _clean(_hit_value(hit, "title")) or original_url
                snippet = _clean(_hit_value(hit, "content"))
                relevance = _relevance(topic, title, snippet)
                if not canonical_url:
                    status = "rejected_irrelevant"
                    reason = "来源 URL 为空或不是 HTTPS"
                    selected = False
                elif relevance <= 0:
                    status = "rejected_irrelevant"
                    reason = "搜索摘要与知识节点没有可识别的语义重合"
                    selected = False
                else:
                    status = "relevant"
                    reason = "已通过 HTTPS 与节点相关性预筛，等待正文抓取"
                    selected = True
                hostname = urlsplit(canonical_url or original_url).hostname or ""
                candidate = {
                        "candidate_id": _stable_id(f"{topic_id}:{canonical_url or original_url}"),
                        "topic_id": topic_id,
                        "title": title,
                        "url": canonical_url or original_url,
                        "domain": hostname.casefold(),
                        "source_type": "web",
                        "language": query_language,
                        "license_name": None,
                        "license_url": None,
                        "authority_tier": "web_discovered",
                        "review_status": status,
                        "review_reason": reason,
                        "selected": selected,
                        "relevance_score": relevance,
                        "metadata": {
                            "query": query,
                            "provider": "configured_web_search",
                            "discovered_at": timestamp,
                            "original_url": original_url,
                            "canonical_url": canonical_url,
                            "snippet": snippet[:1000],
                        },
                    }
                existing_index = candidate_index_by_url.get(dedupe_url)
                if existing_index is None:
                    candidate_index_by_url[dedupe_url] = len(candidates)
                    candidates.append(candidate)
                    if selected:
                        relevant_count += 1
                elif selected and not candidates[existing_index]["selected"]:
                    candidates[existing_index] = candidate
                    relevant_count += 1
                if relevant_count >= max_results:
                    break

    selected_count = sum(1 for item in candidates if item["selected"])
    return {
        "topics": [
            {
                **topic,
                "query": queries_by_topic[topic["topic_id"]][0],
                "english_query": queries_by_topic[topic["topic_id"]][1],
            }
            for topic in topics
        ],
        "source_candidates": candidates,
        "warnings": warnings,
        "metrics": {
            "leaf_count": len(topics),
            "candidate_count": len(candidates),
            "selected_candidate_count": selected_count,
            "search_failure_count": len(warnings),
        },
    }


def discover_leaf_gap_sources(
    build: Mapping[str, Any],
    *,
    topic_ids: set[str],
    round_index: int,
    search_provider: SearchProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Run one new query intent only for leaves that still have a coverage gap."""
    topics = [
        topic
        for topic in confirmed_graph_topics(dict(build.get("graph_draft") or {}))
        if topic["topic_id"] in topic_ids
    ]
    config = dict(build.get("config") or {})
    course = dict(build.get("course_snapshot") or {})
    max_results = max(1, int(config.get("max_search_results_per_leaf") or 6))
    provider = search_provider
    if provider is None:
        from app.services.deepsearch_service import search_web_sources

        provider = search_web_sources
    timestamp = (now or (lambda: datetime.now(timezone.utc)))().isoformat()
    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for topic in topics:
        intents = build_leaf_source_queries(
            course,
            topic,
            content_language=str(config.get("content_language") or "zh-CN"),
        )
        if not intents:
            continue
        intent = intents[min(max(0, int(round_index)), len(intents) - 1)]
        try:
            hits = provider(intent.query, max_results)
        except Exception as exc:
            warnings.append(
                {
                    "code": "SEARCH_PROVIDER_FAILED",
                    "topic_id": topic["topic_id"],
                    "query": intent.query,
                    "message": str(exc),
                }
            )
            continue
        seen_urls: set[str] = set()
        for rank, hit in enumerate(list(hits or []), start=1):
            original_url = _clean(_hit_value(hit, "url"))
            canonical_url = canonical_source_url(original_url)
            dedupe_url = canonical_url or original_url
            if not dedupe_url or dedupe_url in seen_urls:
                continue
            seen_urls.add(dedupe_url)
            candidate = classify_source_candidate(
                intent=intent,
                course=course,
                topic=topic,
                title=_clean(_hit_value(hit, "title")),
                snippet=_clean(_hit_value(hit, "content")),
                url=canonical_url or original_url,
                bocha_rank=rank,
            )
            candidate.update(
                {
                    "candidate_id": _stable_id(
                        f"gap:{round_index}:{topic['topic_id']}:{dedupe_url}"
                    ),
                    "topic_id": topic["topic_id"],
                    "license_name": None,
                    "license_url": None,
                }
            )
            candidate["metadata"] = {
                **dict(candidate.get("metadata") or {}),
                "provider": "configured_web_search",
                "discovered_at": timestamp,
                "original_url": original_url,
                "canonical_url": canonical_url,
                "search_round": int(round_index) + 1,
                "matched_topic_ids": [topic["topic_id"]],
            }
            candidates.append(candidate)
    merged_by_url: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = canonical_source_url(candidate.get("url")) or str(candidate.get("url") or "")
        existing = merged_by_url.get(key)
        if existing is None:
            merged_by_url[key] = candidate
            continue
        matched = {
            *list((existing.get("metadata") or {}).get("matched_topic_ids") or []),
            *list((candidate.get("metadata") or {}).get("matched_topic_ids") or []),
        }
        existing["metadata"] = {
            **dict(existing.get("metadata") or {}),
            "matched_topic_ids": sorted(str(item) for item in matched if str(item)),
        }
        if float((candidate.get("metadata") or {}).get("priority_score") or 0) > float(
            (existing.get("metadata") or {}).get("priority_score") or 0
        ):
            candidate["metadata"] = {
                **dict(candidate.get("metadata") or {}),
                "matched_topic_ids": existing["metadata"]["matched_topic_ids"],
            }
            merged_by_url[key] = candidate
    ranked = rank_source_candidates(list(merged_by_url.values()))
    return {
        "topics": topics,
        "source_candidates": ranked,
        "warnings": warnings,
        "metrics": {
            "searched_leaf_count": len(topics),
            "candidate_count": len(ranked),
            "selected_candidate_count": sum(bool(item.get("selected")) for item in ranked),
            "search_failure_count": len(warnings),
            "search_round": int(round_index) + 1,
        },
    }
