from __future__ import annotations

from app.chat.domain.research_bundle import ResearchBundle, ResearchEvidence
from app.chat.domain.teaching_task_contract import TeachingTaskContract
from app.chat.runtime.research.planner import (
    assess_evidence_coverage,
    build_research_plan,
)


def build_research_bundle(ctx, *, topic: str) -> ResearchBundle:
    existing = getattr(ctx, "research_bundle", None)
    cache = dict(getattr(ctx, "_call_cache", {}) or {})
    if (
        isinstance(existing, ResearchBundle)
        and existing.topic == topic
        and int(getattr(ctx, "_research_cache_size", -1)) == len(cache)
    ):
        return existing
    capability = getattr(ctx, "capability", None)
    source_mode = str(getattr(capability, "source_mode", "none") or "none")
    if source_mode not in {"selected_documents", "course_auto", "none"}:
        source_mode = "selected_documents" if list(getattr(capability, "selected_doc_ids", []) or []) else "none"
    course_evidence: list[ResearchEvidence] = []
    web_evidence: list[ResearchEvidence] = []
    citations: list[dict] = []
    queries: list[str] = []
    seen_citations: set[str] = set()
    for cache_key, result in cache.items():
        tool = str(cache_key).split(":", 1)[0]
        if tool not in {"rag_search", "web_search"} or not isinstance(result, dict) or not result.get("ok"):
            continue
        payload = dict(result.get("payload") or {})
        summary = str(payload.get("answer") if tool == "rag_search" else payload.get("summary") or payload.get("answer") or "").strip()
        sources = [item for item in list(payload.get("sources") or []) if isinstance(item, dict)]
        query = str(payload.get("query") or _query_from_cache_key(cache_key) or "")
        if summary or sources:
            target = course_evidence if tool == "rag_search" else web_evidence
            target.append(ResearchEvidence(
                source_kind="rag" if tool == "rag_search" else "web",
                summary=summary[:8000],
                source=sources[0] if sources else {},
                query=query,
                trust_tier="course" if tool == "rag_search" else _web_trust_tier(sources),
            ))
        for source in sources[:12]:
            identity = _source_identity(source)
            if identity not in seen_citations:
                citations.append(source)
                seen_citations.add(identity)
        if query:
            queries.append(str(query))
    raw_contract = getattr(ctx, "task_contract", None) or {
        "intent": "qa",
        "topic": topic,
        "source_mode": source_mode,
        "selected_document_ids": list(
            getattr(capability, "selected_doc_ids", []) or []
        ),
    }
    try:
        contract = TeachingTaskContract.model_validate(raw_contract)
    except Exception:
        contract = TeachingTaskContract(
            intent="qa",
            topic=topic,
            source_mode=source_mode,
            selected_document_ids=list(
                getattr(capability, "selected_doc_ids", []) or []
            ),
        )
    research_plan = build_research_plan(contract)
    evidence_text = "\n".join([
        *(item.summary for item in course_evidence),
        *(item.summary for item in web_evidence),
        *(str(item.get("title") or "") for item in citations),
    ])
    coverage = assess_evidence_coverage(research_plan, evidence_text)
    bundle = ResearchBundle(
        topic=topic,
        source_mode=source_mode,
        course_evidence=course_evidence,
        web_evidence=web_evidence,
        citations=citations[:24],
        queries=list(dict.fromkeys(queries)),
        quality_summary=(
            f"课程证据 {len(course_evidence)} 条，Web 证据 {len(web_evidence)} 条，"
            f"研究覆盖 {coverage.coverage_ratio:.0%}"
        ),
        missing_evidence=(
            [f"缺少研究维度：{aspect}" for aspect in coverage.missing_aspects]
            if course_evidence or web_evidence
            else ([] if source_mode == "none" else ["未获得必需检索证据"])
        ),
        research_plan=research_plan,
        coverage=coverage,
    ).with_id()
    ctx.research_bundle = bundle
    ctx._research_cache_size = len(cache)
    return bundle


def _query_from_cache_key(cache_key: str) -> str:
    import json

    try:
        payload = json.loads(str(cache_key).split(":", 1)[1])
    except (IndexError, TypeError, json.JSONDecodeError):
        return ""
    return str(payload.get("query") or "") if isinstance(payload, dict) else ""


def _source_identity(source: dict) -> str:
    return "|".join(str(source.get(key) or "") for key in (
        "chunk_id", "document_id", "url", "source_path", "title"
    ))


def _web_trust_tier(sources: list[dict]) -> str:
    urls = " ".join(str(item.get("url") or "").lower() for item in sources)
    if any(suffix in urls for suffix in (".edu", ".gov", "doi.org", "unesco.org")):
        return "authoritative_web"
    return "external_web"
