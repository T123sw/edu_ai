from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class CourseKnowledgeTopic:
    topic_id: str
    title: str
    query: str
    english_query: str
    objective: str


@dataclass(frozen=True)
class CourseSourceCandidate:
    candidate_id: str
    topic_id: str
    title: str
    url: str
    domain: str
    source_type: str
    language: str | None
    license_name: str | None
    license_url: str | None
    authority_tier: str
    review_status: str
    review_reason: str
    selected: bool
    relevance_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CourseKnowledgePlan:
    course_id: str
    course_snapshot: dict[str, Any]
    topics: tuple[CourseKnowledgeTopic, ...]
    graph_draft: dict[str, Any]
    source_candidates: tuple[CourseSourceCandidate, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "course_snapshot": dict(self.course_snapshot),
            "topics": [asdict(item) for item in self.topics],
            "graph_draft": dict(self.graph_draft),
            "source_candidates": [asdict(item) for item in self.source_candidates],
            "warnings": list(self.warnings),
        }


SearchProvider = Callable[[str, int], Sequence[Any]]

_REVIEWED_DOMAIN_POLICIES: dict[str, dict[str, str]] = {
    "zh.wikipedia.org": {"license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/", "language": "zh-CN", "authority": "reviewed_reference"},
    "zh.wikibooks.org": {"license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/", "language": "zh-CN", "authority": "open_textbook"},
    "openstax.org": {"license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "language": "en", "authority": "open_textbook"},
    "ocw.mit.edu": {"license": "CC BY-NC-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/", "language": "en", "authority": "university_oer"},
    "docs.python.org": {"license": "PSF License Version 2", "license_url": "https://docs.python.org/3/license.html", "language": "multi", "authority": "official_documentation"},
    "developer.mozilla.org": {"license": "CC BY-SA 2.5", "license_url": "https://creativecommons.org/licenses/by-sa/2.5/", "language": "multi", "authority": "official_documentation"},
    "oi-wiki.org": {"license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/", "language": "zh-CN", "authority": "community_oer"},
    "www.csunplugged.org": {"license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/", "language": "multi", "authority": "university_oer"},
}


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def derive_course_topics(course: Mapping[str, Any]) -> tuple[CourseKnowledgeTopic, ...]:
    course_id = _normalize_text(course.get("id") or course.get("course_id"))
    title = _normalize_text(course.get("title"))
    objectives = [_normalize_text(item) for item in course.get("objectives") or []]
    seeds = [item for item in objectives if item] or [title]
    audience = _normalize_text(course.get("audience"))
    chinese_scope = "(site:zh.wikipedia.org OR site:zh.wikibooks.org OR site:oi-wiki.org OR site:csunplugged.org)"
    english_scope = "(site:openstax.org OR site:ocw.mit.edu OR site:docs.python.org OR site:developer.mozilla.org)"
    topics: list[CourseKnowledgeTopic] = []
    for position, objective in enumerate(seeds[:12]):
        topic_title = objective[:80]
        topic_id = _stable_id("topic", f"{course_id}:{position}:{topic_title}")
        query = " ".join(value for value in (title, topic_title, audience, "lang:zh-CN", "开放教材 课程资料", chinese_scope) if value)
        english_query = " ".join(value for value in (title, topic_title, audience, "lang:en", "open educational resource tutorial", english_scope) if value)
        topics.append(CourseKnowledgeTopic(topic_id, topic_title, query, english_query, objective))
    return tuple(topics)


def build_course_graph_draft(course: Mapping[str, Any], topics: Sequence[CourseKnowledgeTopic]) -> dict[str, Any]:
    title = _normalize_text(course.get("title")) or "课程"
    module_label = re.sub(r"(?:入门|基础|教程|课程)$", "", title).strip() or f"{title}核心知识"
    leaves = [
        {
            "id": topic.topic_id,
            "label": topic.title,
            "children": [],
            "data": {"level": 2, "type": "knowledge_point", "summary": topic.objective, "hasChildren": False, "document_ids": []},
        }
        for topic in topics
    ]
    return {
        "id": "root",
        "label": f"{title}课程知识图谱",
        "children": [{
            "id": _stable_id("module", f"{course.get('id')}:{module_label}"),
            "label": module_label,
            "children": leaves,
            "data": {"level": 1, "type": "knowledge_module", "summary": f"{title}的核心概念与技能结构", "hasChildren": bool(leaves)},
        }],
        "data": {"level": 0, "type": "course", "summary": _normalize_text(course.get("description")), "hasChildren": bool(leaves)},
    }


def _domain_policy(url: str) -> tuple[str, dict[str, str] | None]:
    parsed = urlparse(str(url or ""))
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if parsed.scheme != "https" or not host:
        return host, None
    for domain, policy in _REVIEWED_DOMAIN_POLICIES.items():
        if host == domain or host.endswith(f".{domain}"):
            return host, policy
    return host, None


def _relevance(topic: CourseKnowledgeTopic, title: str, content: str) -> float:
    haystack = f"{title} {content}".casefold()
    terms = [term for term in re.split(r"[\s，。；、:：]+", topic.title.casefold()) if len(term) >= 2]
    for prefix in ("理解", "掌握", "了解", "认识", "学会", "分析", "应用", "运用"):
        if topic.title.startswith(prefix) and len(topic.title) > len(prefix) + 1:
            terms.append(topic.title[len(prefix):].casefold())
    if not terms:
        return 0.5
    return round(sum(1 for term in terms if term in haystack) / len(terms), 4)


def preview_course_knowledge_plan(
    course: Mapping[str, Any],
    *,
    search_provider: SearchProvider | None = None,
    max_results_per_topic: int = 6,
) -> CourseKnowledgePlan:
    course_snapshot = {key: course.get(key) for key in ("id", "title", "description", "audience", "objectives", "language", "difficulty", "revision")}
    course_id = _normalize_text(course_snapshot.get("id"))
    topics = derive_course_topics(course)
    graph_draft = build_course_graph_draft(course, topics)
    warnings: list[str] = []
    candidates: list[CourseSourceCandidate] = []
    seen_plan_urls: set[str] = set()

    if search_provider is None:
        warnings.append("当前未启用来源搜索服务；构建时将通过模型补充缺失资料。")
    else:
        for topic in topics[:6]:
            approved_for_topic = 0

            def collect_hits(hits: Sequence[Any] | None, *, stage: str) -> None:
                nonlocal approved_for_topic
                if hits is None:
                    warnings.append(f"“{topic.title}”{stage}检索没有返回结果")
                    return
                for hit in hits:
                    url = _normalize_text(getattr(hit, "url", None) or (hit.get("url") if isinstance(hit, Mapping) else ""))
                    if not url or url in seen_plan_urls:
                        continue
                    seen_plan_urls.add(url)
                    hit_title = _normalize_text(getattr(hit, "title", None) or (hit.get("title") if isinstance(hit, Mapping) else "") or url)
                    content = _normalize_text(getattr(hit, "content", None) or (hit.get("content") if isinstance(hit, Mapping) else ""))
                    domain, policy = _domain_policy(url)
                    relevance = _relevance(topic, hit_title, content)
                    approved = policy is not None and relevance > 0
                    if approved:
                        approved_for_topic += 1
                    reason = "来源域名、HTTPS 与许可策略已通过预审" if approved else ("未找到可验证的开放许可策略" if policy is None else "与课程目标相关性不足")
                    candidates.append(CourseSourceCandidate(
                        candidate_id=_stable_id("source", f"{topic.topic_id}:{url}"),
                        topic_id=topic.topic_id,
                        title=hit_title,
                        url=url,
                        domain=domain,
                        source_type="web",
                        language=policy.get("language") if policy else None,
                        license_name=policy.get("license") if policy else None,
                        license_url=policy.get("license_url") if policy else None,
                        authority_tier=policy.get("authority", "unreviewed") if policy else "unreviewed",
                        review_status="approved" if approved else "rejected",
                        review_reason=reason,
                        selected=approved,
                        relevance_score=relevance,
                        metadata={"snippet": content[:1000], "acquisition_stage": stage},
                    ))

            try:
                collect_hits(search_provider(topic.query, max_results_per_topic), stage="chinese")
            except Exception as exc:
                warnings.append(f"“{topic.title}”中文来源检索失败：{exc}")
            if approved_for_topic < 3:
                try:
                    collect_hits(search_provider(topic.english_query, max_results_per_topic), stage="english_fallback")
                except Exception as exc:
                    warnings.append(f"“{topic.title}”英文补充检索失败：{exc}")

    if not any(item.selected for item in candidates):
        warnings.append("尚未发现通过许可与相关性预审的来源；构建时会按质量门禁生成中文补充资料。")
    return CourseKnowledgePlan(course_id, course_snapshot, topics, graph_draft, tuple(candidates), tuple(dict.fromkeys(warnings)))
