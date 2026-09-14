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
    is_authoritative_source_domain,
    is_low_quality_source,
    is_non_instructional_source_title,
    rank_source_candidates,
)


SearchProvider = Callable[[str, int], Sequence[Any]]
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_id(value: str) -> str:
    return f"source-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _matches_domain(hostname: str, domains: Sequence[str]) -> bool:
    normalized = _clean(hostname).casefold().strip(".")
    return any(
        normalized == _clean(domain).casefold().strip(".")
        or normalized.endswith("." + _clean(domain).casefold().strip("."))
        for domain in domains
        if _clean(domain)
    )


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



def execution_topics(build):
    topics = confirmed_graph_topics(dict(build.get("graph_draft") or {}))
    selected = build.get("selected_topic_ids")
    if selected is None:
        selected_topics = topics
    else:
        allowed = set(selected)
        if not allowed.issubset({t["topic_id"] for t in topics}):
            raise ValueError("补充清单与目录不一致，请重新确认")
        selected_topics = [topic for topic in topics if topic["topic_id"] in allowed]
    intent = dict(build.get("intent_contract") or {})
    contract_requirements = [
        item
        for item in intent.get("requirements") or []
        if isinstance(item, Mapping)
    ]
    common_requirements = {
        "source_policy": dict(intent.get("source_policy") or {}),
        "deliverables": list(intent.get("deliverables") or []),
        "depth_profile": dict(intent.get("depth_profile") or {}),
        "audience": str((intent.get("course_profile") or {}).get("audience") or ""),
        "requirement_ids": [
            str(item.get("requirement_id") or "")
            for item in contract_requirements
            if item.get("requirement_id")
        ],
    }
    requirements = build.get("topic_requirements") or {}
    return [
        {
            **topic,
            "material_namespace": build.get("build_id", ""),
            **common_requirements,
            **requirements.get(topic["topic_id"], {}),
        }
        for topic in selected_topics
    ]

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


def _curated_course_candidates(
    course: Mapping[str, Any], *, discovered_at: str
) -> list[dict[str, Any]]:
    """Return small, auditable seeds; web search remains responsible for gaps."""

    title = _clean(course.get("title"))
    if "操作系统" not in title and "operating system" not in title.casefold():
        return []
    seeds = [
        {
            "title": "xv6: a simple, Unix-like teaching operating system",
            "url": "https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf",
            "content_format_hint": "pdf",
        },
        {
            "title": "Operating Systems: Three Easy Pieces",
            "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
            "content_format_hint": "html",
            "linked_chapter_urls": [
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-intro.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-cv.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-api.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys-policy.pdf",
            ],
        },
    ]
    return [
        {
            "candidate_id": _stable_id(f"course:{seed['url']}"),
            "topic_id": None,
            "title": seed["title"],
            "url": seed["url"],
            "domain": urlsplit(seed["url"]).hostname,
            "source_type": "web",
            "language": "en",
            "license_name": None,
            "license_url": None,
            "authority_tier": "authoritative_source",
            "review_status": "relevant",
            "review_reason": "命中经审核的课程级权威来源目录，等待下载与正文校验",
            "selected": True,
            "relevance_score": 1.0,
            "metadata": {
                "query": "curated_authoritative_course_source",
                "provider": "curated_source_catalog",
                "discovered_at": discovered_at,
                "original_url": seed["url"],
                "canonical_url": seed["url"],
                "discovery_scope": "course",
                "discovery_intent": "complete_textbook_pdf"
                if seed["content_format_hint"] == "pdf"
                else "complete_textbook_html",
                "resource_kind": "textbook",
                "content_format_hint": seed["content_format_hint"],
                "linked_chapter_urls": list(seed.get("linked_chapter_urls") or []),
                "course_relevance": 1.0,
                "topic_relevance": 1.0,
                "completeness_score": 1.0,
                "priority_score": 2.0,
                "institutional_authority": True,
                "low_quality_source": False,
                "non_instructional": False,
            },
        }
        for seed in seeds
    ]


def _queries(
    *,
    course: Mapping[str, Any],
    topic: Mapping[str, Any],
    content_language: str,
) -> list[tuple[str, str]]:
    # Initial discovery uses the first two planned intents. Later gap rounds can
    # consume the fallback intent without multiplying the normal search load.
    return [
        (intent.query, intent.language)
        for intent in build_leaf_source_queries(
            course, topic, content_language=content_language
        )[:2]
    ]


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
    candidates_by_url: dict[str, dict[str, Any]] = {
        str(item["url"]): item
        for item in _curated_course_candidates(course, discovered_at=timestamp)
    }
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
            elif not bool((candidate.get("metadata") or {}).get("institutional_authority")):
                candidate["selected"] = False
                candidate["review_status"] = "rejected_irrelevant"
                candidate["review_reason"] = "课程级教材必须来自高校、政府或已知官方文档站点"
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
        selected_domains = {
            str(item.get("domain") or "")
            for item in ranked
            if item.get("selected") and item.get("domain")
        }
        if len(selected_domains) >= max_textbooks:
            break

    ranked = rank_source_candidates(list(candidates_by_url.values()))
    selected_seen = 0
    selected_domains: set[str] = set()
    for candidate in ranked:
        if not candidate.get("selected"):
            continue
        domain = str(candidate.get("domain") or "")
        if domain in selected_domains:
            candidate["selected"] = False
            candidate["review_status"] = "rejected_irrelevant"
            candidate["review_reason"] = "同一教材站点只保留一个课程级候选"
            continue
        if selected_seen >= max_textbooks:
            candidate["selected"] = False
            candidate["review_status"] = "rejected_irrelevant"
            candidate["review_reason"] = "已达到在线教材候选上限"
            continue
        selected_seen += 1
        selected_domains.add(domain)
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
    topics = execution_topics(build)
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
                source_policy = dict(topic.get("source_policy") or {})
                required_domains = list(source_policy.get("required_domains") or [])
                preferred_domains = list(source_policy.get("preferred_domains") or [])
                hostname = (urlsplit(canonical_url or original_url).hostname or "").casefold()
                required_match = _matches_domain(hostname, required_domains) if required_domains else None
                preferred_match = _matches_domain(hostname, preferred_domains) if preferred_domains else None
                low_quality_source = is_low_quality_source(hostname, title, snippet)
                non_instructional = is_non_instructional_source_title(title)
                institutional_authority = is_authoritative_source_domain(hostname)
                if not canonical_url:
                    status = "rejected_irrelevant"
                    reason = "来源 URL 为空或不是 HTTPS"
                    selected = False
                elif non_instructional:
                    status = "rejected_irrelevant"
                    reason = "来源是课程简介或教学大纲，不足以作为知识点正文"
                    selected = False
                elif low_quality_source:
                    status = "rejected_irrelevant"
                    reason = "来源属于低质量文档镜像或下载站，已在抓取前拒绝"
                    selected = False
                elif required_match is False:
                    status = "rejected_irrelevant"
                    reason = "来源不在教师限定的必选域名内"
                    selected = False
                elif preferred_match is False and "site:" in query.casefold():
                    status = "rejected_irrelevant"
                    reason = "优先来源检索阶段不接收搜索服务返回的站外结果"
                    selected = False
                elif relevance <= 0:
                    status = "rejected_irrelevant"
                    reason = "搜索摘要与知识节点没有可识别的语义重合"
                    selected = False
                else:
                    status = "relevant"
                    reason = "已通过 HTTPS 与节点相关性预筛，等待正文抓取"
                    selected = True
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
                        "authority_tier": (
                            "teacher_required_source"
                            if required_match
                            else "teacher_preferred_source"
                            if preferred_match
                            else "authoritative_source"
                            if institutional_authority
                            else "web_discovered"
                        ),
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
                            "topic_title": _clean(topic.get("title")),
                            "topic_objective": _clean(topic.get("objective")),
                            "required_domain_match": required_match,
                            "preferred_domain_match": preferred_match,
                            "institutional_authority": institutional_authority,
                            "low_quality_source": low_quality_source,
                            "non_instructional": non_instructional,
                            "requirement_ids": list(topic.get("requirement_ids") or []),
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
        for topic in execution_topics(build)
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
