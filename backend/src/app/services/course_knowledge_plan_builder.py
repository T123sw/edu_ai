"""Build and publish a quality-gated course knowledge graph from a semantic plan."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import time
from contextlib import nullcontext
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.course_generated_material import generate_reviewed_supplement
from app.services.course_knowledge_builder import _canonical_path, _robots_allows, _safe_material_filename, utc_now
from app.services.course_knowledge_coverage import calculate_leaf_coverage
from app.services.course_knowledge_source_discovery import (
    canonical_source_url,
    execution_topics,
    discover_course_knowledge_sources,
    discover_course_textbook_sources,
    discover_leaf_gap_sources,
)
from app.services.course_knowledge_source_ingestion import (
    SourceIngestionError,
    fetch_source,
    parse_html_source,
    parse_pdf_source,
)
from app.services.course_knowledge_textbook_mapping import map_textbook_chunks_to_graph
from app.services.course_knowledge_quality_gate import evaluate_course_knowledge_quality
from app.services.course_knowledge_source_policy import is_non_instructional_source_title
from app.services.job_store import EduJob, JobKind, JobStatus, create_job, update_job
from core.course_storage import LIBRARY_TYPE_COURSE, CourseStorageManager


PLAN_BUILDER_VERSION = "course-kb-plan-v2"
MIN_DOCUMENTS_PER_LEAF = 3


class CourseKnowledgeBuildCancelled(RuntimeError):
    """Raised at safe phase boundaries when the durable task was canceled."""


def _effective_build_config(build: Mapping[str, Any]) -> dict[str, Any]:
    config = dict(build.get("config") or {})
    intent = build.get("intent_contract")
    if isinstance(intent, Mapping):
        source_policy = intent.get("source_policy")
        if isinstance(source_policy, Mapping):
            config["ai_supplement_enabled"] = bool(
                source_policy.get("allow_ai_fallback", False)
            )
    return config


def _merge_source_candidates(
    existing: list[Mapping[str, Any]],
    additions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one database row per canonical URL while retaining all topic hits."""

    merged: list[dict[str, Any]] = [dict(item) for item in existing]
    positions = {
        canonical_source_url(item.get("url")) or str(item.get("url") or ""): index
        for index, item in enumerate(merged)
    }
    for raw in additions:
        candidate = dict(raw)
        key = canonical_source_url(candidate.get("url")) or str(candidate.get("url") or "")
        if not key or key not in positions:
            positions[key] = len(merged)
            merged.append(candidate)
            continue
        index = positions[key]
        current = merged[index]
        matched_topics = {
            str(item)
            for item in (
                *(dict(current.get("metadata") or {}).get("matched_topic_ids") or []),
                *(dict(candidate.get("metadata") or {}).get("matched_topic_ids") or []),
                current.get("topic_id"),
                candidate.get("topic_id"),
            )
            if item
        }
        current_priority = (
            bool(current.get("selected")),
            2 if current.get("review_status") == "ready" else 1 if current.get("review_status") == "relevant" else 0,
            float(dict(current.get("metadata") or {}).get("priority_score") or 0),
        )
        candidate_priority = (
            bool(candidate.get("selected")),
            2 if candidate.get("review_status") == "ready" else 1 if candidate.get("review_status") == "relevant" else 0,
            float(dict(candidate.get("metadata") or {}).get("priority_score") or 0),
        )
        winner = candidate if candidate_priority > current_priority else current
        winner = dict(winner)
        winner["metadata"] = {
            **dict(winner.get("metadata") or {}),
            "matched_topic_ids": sorted(matched_topics),
        }
        merged[index] = winner
    return merged


def _update_candidate_in_memory(
    candidates: list[dict[str, Any]],
    candidate_id: str,
    *,
    review_status: str,
    review_reason: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    for candidate in candidates:
        if str(candidate.get("candidate_id") or "") != candidate_id:
            continue
        candidate["review_status"] = review_status
        candidate["review_reason"] = review_reason
        candidate["metadata"] = {
            **dict(candidate.get("metadata") or {}),
            **dict(metadata or {}),
        }
        return


def get_postgres_knowledge_repository():
    # Avoid importing application configuration while pure planning helpers are
    # imported by tests and offline evaluators. Keep this public compatibility
    # seam because builder tests and deployments patch it.
    from app.persistence.dependencies import (
        get_postgres_knowledge_repository as resolve_repository,
    )

    return resolve_repository()


def _knowledge_repository():
    return get_postgres_knowledge_repository()


def _ensure_required_artifact_generation(
    deficits: list[tuple[Mapping[str, Any], int]],
    *,
    topics: list[Mapping[str, Any]],
    persisted: list[Mapping[str, Any]],
    ai_enabled: bool,
    maximum_ai: int,
) -> None:
    """Schedule one reviewed artifact document when the teacher allows AI."""

    if not ai_enabled or maximum_ai < 1:
        return
    for topic in topics:
        deliverables = [
            item
            for item in topic.get("deliverables") or []
            if isinstance(item, Mapping) and item.get("hardness", "hard") == "hard"
        ]
        if not deliverables or not bool(
            dict(topic.get("source_policy") or {}).get("allow_ai_fallback", False)
        ):
            continue
        required_counts = {
            str(item.get("requirement_id") or ""): int(item.get("count") or 0)
            for item in deliverables
        }
        topic_id = str(topic.get("topic_id") or "")
        topic_scoped = any(item.get("application") == "topic" for item in deliverables)
        existing_counts: dict[str, int] = {}
        existing_artifacts = [
            artifact
            for document in persisted
            for artifact in document.get("learning_artifacts") or []
            if isinstance(artifact, Mapping)
            and artifact.get("validation_status", "passed") == "passed"
            and (
                not topic_scoped
                or str(artifact.get("topic_id") or document.get("scope_id") or "") == topic_id
            )
        ]
        for artifact in existing_artifacts:
            requirement_id = str(artifact.get("requirement_id") or "")
            existing_counts[requirement_id] = existing_counts.get(requirement_id, 0) + int(
                artifact.get("count") or 1
            )
        if all(
            existing_counts.get(requirement_id, 0) >= count
            for requirement_id, count in required_counts.items()
        ):
            continue
        if not any(
            str(item.get("topic_id") or "") == topic_id and sequence == 1
            for item, sequence in deficits
        ):
            deficits.append(({**dict(topic), "artifact_generation_only": True}, 1))
        if not topic_scoped:
            return


def _reviewed_generation_resume_limit(
    topic: Mapping[str, Any],
    *,
    ai_budget: int,
    ai_enabled: bool,
    maximum_ai: int,
) -> int:
    """Keep reviewed teaching artifacts across retries, even after sources fill the leaf.

    Source acquisition can remove the numeric content deficit on a later run,
    but it does not replace teacher-requested cases, exercises, explanations,
    or labs already produced and independently reviewed for this build.
    """

    if not ai_enabled or maximum_ai < 1:
        return ai_budget
    requires_generated_artifacts = bool(
        dict(topic.get("source_policy") or {}).get("allow_ai_fallback", False)
        and any(
            isinstance(item, Mapping) and item.get("hardness", "hard") == "hard"
            for item in topic.get("deliverables") or []
        )
    )
    return max(ai_budget, 1 if requires_generated_artifacts else 0)


def submit_course_knowledge_plan_build_job(
    *, course_id: str, owner_user_id: str, build_id: str, retry: bool = False
) -> EduJob:
    repository = _knowledge_repository()
    build = repository.get_build(build_id)
    if build is None or str(build.get("library_id") or "") != course_id:
        raise ValueError("知识库构建计划不存在")
    if build.get("knowledge_proposal"):
        from app.services.course_knowledge_proposals import check_baseline
        check_baseline(repository, build)
    revision = int(build.get("revision") or 0)
    if (
        not build.get("graph_confirmed_at")
        or int(build.get("confirmed_graph_revision") or 0) != revision
    ):
        raise ValueError("知识图谱尚未确认，不能启动正式构建")
    from app.services.platform_task_handlers import enqueue_platform_task
    from app.services.runtime_config_resolver import runtime_config_resolver

    if retry:
        repository.requeue_build(build_id)
    else:
        repository.queue_build(build_id, selected_source_count=0)
    try:
        job = create_job(
            kind=JobKind.BUILD_KNOWLEDGE_INDEX,
            owner_user_id=owner_user_id,
            course_id=course_id,
            input_summary={"build_id": build_id, "selected_source_count": 0},
        )
        queued_job = enqueue_platform_task(
            job=job,
            workflow_type="course_knowledge_plan_build",
            command={
                "course_id": course_id,
                "build_id": build_id,
                # A small course can still require several generation and
                # independent-review calls when no open sources qualify.
                "deadline_seconds": 1800,
            },
            runtime_config_snapshot=runtime_config_resolver.capture_snapshot(owner_user_id),
        )
        if queued_job.status == JobStatus.FAILED:
            repository.update_build(build_id, status="failed", phase="enqueue_failed", progress=100, error={"code": "BUILD_ENQUEUE_FAILED", "message": queued_job.error_message or "任务入队失败"})
        return queued_job
    except Exception as exc:
        repository.update_build(build_id, status="failed", phase="enqueue_failed", progress=100, error={"code": "BUILD_ENQUEUE_FAILED", "message": str(exc)})
        raise


def _extract_reviewed_page(
    client: httpx.Client,
    candidate: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    url = str(candidate.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("来源必须使用 HTTPS")
    if not _robots_allows(client, url):
        raise PermissionError("来源 robots.txt 不允许抓取")
    download_deadline = time.monotonic() + 20
    chunks: list[bytes] = []
    downloaded_bytes = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        if "html" not in str(response.headers.get("content-type") or "").casefold():
            raise ValueError("来源不是可解析的网页正文")
        final_response_url = str(response.url)
        encoding = response.encoding or "utf-8"
        for chunk in response.iter_bytes():
            if time.monotonic() > download_deadline:
                raise TimeoutError("来源正文下载超过 20 秒总时限")
            downloaded_bytes += len(chunk)
            if downloaded_bytes > 3 * 1024 * 1024:
                raise ValueError("来源网页超过 3 MiB，拒绝作为单篇知识点正文")
            chunks.append(chunk)
    soup = BeautifulSoup(b"".join(chunks).decode(encoding, errors="replace"), "html.parser")
    for element in soup.select("script, style, nav, header, footer, aside, form, noscript"):
        element.decompose()
    main = soup.select_one("main, article, [role='main'], .md-content, #content") or soup.body
    if parsed.fragment:
        fragment = soup.find(id=parsed.fragment)
        if fragment is not None:
            main = (
                fragment
                if fragment.name == "section"
                else fragment.find_parent("section") or fragment.parent or fragment
            )
    if main is None:
        raise ValueError("来源页面没有可识别的正文")
    title = str(candidate.get("title") or (soup.title.string if soup.title and soup.title.string else url)).strip()
    lines = [re.sub(r"\s+", " ", value).strip() for value in main.get_text("\n").splitlines()]
    content = "\n\n".join(value for value in lines if value)
    if len(content) < 300:
        raise ValueError("来源正文过短")
    content = content[:60000]
    final_url = canonical_source_url(final_response_url or url)
    if not final_url:
        raise ValueError("来源最终重定向 URL 不是 HTTPS")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return title, content, final_url, content_hash


def _update_saved_record(
    *,
    manager: CourseStorageManager,
    course_id: str,
    relative_path: str,
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    index = manager.get_knowledge_base_index(course_id)
    record = next(item for item in reversed(index) if _canonical_path(item.get("path")) == _canonical_path(relative_path))
    record.update(dict(fields))
    manager.save_knowledge_base_index(course_id, index)
    return record


_GENERIC_TOPIC_TERMS = {
    "基础",
    "基本",
    "概念",
    "原理",
    "机制",
    "方法",
    "过程",
    "问题",
    "分析",
    "理解",
    "掌握",
    "解释",
    "比较",
    "操作",
}


def _direct_topic_terms(topic_title: str) -> set[str]:
    """Extract leaf-specific terms without counting generic objective wording."""

    normalized = str(topic_title or "").casefold()
    latin_terms = set(re.findall(r"[a-z][a-z0-9+#.-]{1,}", normalized))
    chinese_parts = re.split(
        r"(?:以及|及其|与|和|及|的|、|/|[：:，,；;（）()\s]+)",
        "".join(re.findall(r"[\u4e00-\u9fff/、，；：与和及的（）()]+", normalized)),
    )
    chinese_terms: set[str] = set()
    for raw_part in chinese_parts:
        part = raw_part
        for generic in ("基本概念", "核心概念", "基本原理", "基本机制"):
            part = part.replace(generic, "")
        if len(part) >= 2 and part not in _GENERIC_TOPIC_TERMS:
            chinese_terms.add(part)
    terms = latin_terms | chinese_terms
    aliases = {
        "容器资源隔离": {"container", "resource", "isolation", "cgroup"},
        "资源隔离": {"resource", "isolation", "cgroup"},
        "内存": {"memory"},
        "调度": {"scheduling", "scheduler"},
        "死锁": {"deadlock"},
        "线程": {"thread"},
        "进程": {"process"},
        "虚拟内存": {"virtual memory"},
        "页面置换": {"page replacement"},
        "地址转换": {"address translation"},
    }
    compact_title = re.sub(r"\s+", "", normalized)
    for chinese_term, translated in aliases.items():
        if chinese_term in compact_title:
            terms.update(translated)
    for term in tuple(terms):
        if re.fullmatch(r"[a-z][a-z0-9+#.-]*s", term) and len(term) > 3:
            terms.add(term[:-1])
    return terms


def _source_semantic_evidence(candidate: Mapping[str, Any], content: str) -> tuple[bool, float]:
    metadata = dict(candidate.get("metadata") or {})
    title = re.sub(r"\s+", "", str(metadata.get("topic_title") or "")).casefold()
    objective = str(metadata.get("topic_objective") or "")
    subject = f"{metadata.get('topic_title') or ''} {objective}".casefold()
    latin_terms = set(re.findall(r"[a-z0-9+#.-]{2,}", subject))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", subject))
    chinese_terms = {
        chinese[index : index + 2]
        for index in range(max(0, len(chinese) - 1))
    }
    terms = {item for item in (*latin_terms, *chinese_terms) if item}
    direct_terms = _direct_topic_terms(str(metadata.get("topic_title") or ""))
    if not terms or not direct_terms:
        return True, 1.0
    normalized_content = str(content or "").casefold()
    compact_content = re.sub(r"\s+", "", normalized_content)
    matched = sum(1 for term in terms if term in normalized_content)
    score = round(matched / len(terms), 4)
    direct_matches = {term for term in direct_terms if term in normalized_content}
    specialized_latin = {
        term for term in direct_terms if re.search(r"[a-z]", term)
    }
    required_direct_matches = 1 if len(direct_terms) == 1 else 2
    if specialized_latin:
        required_direct_matches = min(
            required_direct_matches,
            max(1, min(2, len(specialized_latin))),
        )

    relevant_chars = 0
    relevant_blocks = 0
    for block in re.split(r"\n\s*\n", str(content or "")):
        normalized_block = block.casefold()
        if any(term in normalized_block for term in direct_terms):
            relevant_chars += len(block.strip())
            relevant_blocks += 1

    exact_title = bool(title and title in compact_content)
    direct_enough = len(direct_matches) >= required_direct_matches
    substantive = relevant_chars >= 350 and relevant_blocks >= 2
    passed = direct_enough and substantive and (
        exact_title
        or (matched >= 3 and score >= 0.3)
        or len(direct_matches) >= 3
    )
    return bool(passed), score


def _persist_candidate(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    candidate: Mapping[str, Any],
    seen_final_urls: set[str] | None = None,
    seen_content_hashes: set[str] | None = None,
) -> dict[str, Any]:
    url = str(candidate.get("url") or "").strip()
    scope_id = str(candidate.get("topic_id") or "")
    for existing in manager.get_knowledge_base_index(course_id):
        if (
            str(existing.get("source_url") or existing.get("url") or "").strip() == url
            and str(existing.get("scope_id") or "") == scope_id
            and existing.get("status") == "ready"
        ):
            return {
                "document_id": str(existing.get("id") or ""),
                "scope_id": scope_id,
                "source_url": str(existing.get("source_final_url") or existing.get("source_url") or url),
                "final_url": str(existing.get("source_final_url") or existing.get("source_url") or url),
                "reused": True,
                "source_type": "web",
                "content_hash": existing.get("content_hash"),
                "content_chars": int(existing.get("content_chars") or 0),
                "chunk_count": int(existing.get("chunk_count") or 0),
                "source_domain": existing.get("source_domain"),
                "authority_tier": existing.get("authority_tier"),
                "semantic_evidence_passed": existing.get("semantic_evidence_passed"),
                "semantic_evidence_score": existing.get("semantic_evidence_score"),
                "provenance_ok": bool(existing.get("content_hash") and (existing.get("source_final_url") or existing.get("source_url"))),
            }
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/2.0 (+source-attribution)"}
    timeout = httpx.Timeout(connect=8, read=8, write=8, pool=5)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        title, content, final_url, content_hash = _extract_reviewed_page(client, candidate)
    if is_non_instructional_source_title(title):
        raise ValueError("来源页面属于新闻、通知或教学管理内容，不是知识点正文")
    semantic_evidence_passed, semantic_evidence_score = _source_semantic_evidence(
        candidate, content
    )
    if not semantic_evidence_passed:
        raise ValueError("来源正文与目标知识点缺少足够语义证据")
    if seen_final_urls is not None and final_url in seen_final_urls:
        raise ValueError("来源最终 URL 与本次构建中的其他页面重复")
    if seen_content_hashes is not None and content_hash in seen_content_hashes:
        raise ValueError("来源正文与本次构建中的其他页面重复")
    license_name = str(candidate.get("license_name") or "")
    license_url = str(candidate.get("license_url") or "")
    filename = _safe_material_filename("plan", title, f"{scope_id}:{url}")
    attribution = [
        f"> 来源：[{candidate.get('domain') or url}]({final_url})  ",
        f"> 获取时间：{utc_now()}  ",
    ]
    if license_name or license_url:
        attribution.append(f"> 许可：[{license_name or '来源声明'}]({license_url})  ")
    body = f"# {title}\n\n" + "\n".join(attribution) + f"\n\n{content}\n"
    relative_path = manager.save_knowledge_base_file(
        course_id, body.encode("utf-8"), filename,
        scope_type="knowledge_point", scope_id=scope_id, library_type=LIBRARY_TYPE_COURSE,
    )
    if not relative_path:
        raise OSError("保存课程来源失败")
    full_path = manager.get_course_dir(course_id) / relative_path
    import_result = rag_system.import_document(
        str(full_path), force_reimport=True, owner=owner_user_id,
        metadata_overrides={"course_id": course_id, "library_type": LIBRARY_TYPE_COURSE, "scope_type": "knowledge_point", "scope_id": scope_id, "knowledge_node_id": scope_id},
    )
    record = _update_saved_record(
        manager=manager, course_id=course_id, relative_path=relative_path,
        fields={
            "url": final_url, "source_url": final_url, "source_title": title,
            "source_domain": str(candidate.get("domain") or parsed_domain(final_url)),
            "source_site_name": str(candidate.get("domain") or parsed_domain(final_url)),
            "source_license": license_name, "source_license_url": license_url,
            "source_language": candidate.get("language"), "content_language": candidate.get("language"),
            "translation_notice": "原文入库，未经机器翻译", "authority_tier": candidate.get("authority_tier"),
            "generated_by": PLAN_BUILDER_VERSION, "retrieved_at": utc_now(), "doc_kind": "web",
            "source_type": "web", "status": "received", "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
            "source_query": (candidate.get("metadata") or {}).get("query"),
            "source_discovery_intent": (candidate.get("metadata") or {}).get("discovery_intent"),
            "matched_topic_ids": (candidate.get("metadata") or {}).get("matched_topic_ids") or [scope_id],
            "source_original_url": url,
            "source_final_url": final_url,
            "content_hash": content_hash,
            "content_chars": len(content),
            "semantic_evidence_passed": semantic_evidence_passed,
            "semantic_evidence_score": semantic_evidence_score,
        },
    )
    if seen_final_urls is not None:
        seen_final_urls.add(final_url)
    if seen_content_hashes is not None:
        seen_content_hashes.add(content_hash)
    return {
        "document_id": record["id"],
        "scope_id": scope_id,
        "source_url": final_url,
        "reused": False,
        "source_type": "web",
        "content_hash": content_hash,
        "content_chars": len(content),
        "chunk_count": int(import_result.get("chunk_count") or 0),
        "final_url": final_url,
        "source_domain": str(candidate.get("domain") or parsed_domain(final_url)),
        "authority_tier": candidate.get("authority_tier"),
        "semantic_evidence_passed": semantic_evidence_passed,
        "semantic_evidence_score": semantic_evidence_score,
    }


def _generate_and_persist_supplement(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    course_title: str,
    topic: Mapping[str, Any],
    sequence: int,
    persistence_lock: RLock | None = None,
    fallback_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    leaf_title = str(topic.get("title") or "知识点")
    scope_id = str(topic.get("topic_id") or "")
    from app.services.runtime_config_resolver import runtime_config_resolver

    resolved = runtime_config_resolver.resolve("llm", owner_user_id=owner_user_id)
    llm_config = {
        "model_name": resolved.get("model"),
        "api_base": resolved.get("base_url"),
        "api_key": resolved.get("api_key"),
        "timeout_seconds": resolved.get("timeout_seconds"),
        # Reasoning-capable models account for hidden reasoning inside the
        # completion budget. Structured cases plus exercises otherwise risk a
        # successful HTTP response whose visible content is empty.
        "max_tokens": 8192,
        # This phase needs deterministic schema adherence, not a long hidden
        # chain of thought. DeepSeek thinking mode is enabled by default and
        # can consume the whole completion budget before emitting Markdown.
        "thinking": "disabled",
    }
    supplement = generate_reviewed_supplement(
        course_title=course_title,
        leaf_title=leaf_title,
        sequence=sequence,
        call_model=lambda prompt: str(rag_system._call_llm(prompt, llm_config=llm_config)),
        topic_id=scope_id,
        deliverables=(
            [dict(item) for item in topic.get("deliverables") or []]
            if sequence == 1
            else []
        ),
        additional_requirements=str(topic.get("requested_materials") or ""),
    )
    identity = f"{course_id}:{scope_id}:{sequence}"
    if topic.get("material_namespace"):
        identity += ":" + str(topic["material_namespace"])
    filename = _safe_material_filename("generated", supplement.title, identity)
    body = (
        f"> **AI 生成补充资料**：本资料由系统模型生成，用于补齐“{leaf_title}”的课程知识库覆盖；"
        f"未附带外部来源、引用或许可证。独立质量审查得分：{supplement.review_score}/100。\n\n"
        f"{supplement.content}\n"
    )
    with persistence_lock or nullcontext():
        relative_path = manager.save_knowledge_base_file(
            course_id, body.encode("utf-8"), filename,
            scope_type="knowledge_point", scope_id=scope_id, library_type=LIBRARY_TYPE_COURSE,
        )
        if not relative_path:
            raise OSError("保存模型补充资料失败")
        full_path = manager.get_course_dir(course_id) / relative_path
        import_result = rag_system.import_document(
            str(full_path), force_reimport=True, owner=owner_user_id,
            metadata_overrides={"course_id": course_id, "library_type": LIBRARY_TYPE_COURSE, "scope_type": "knowledge_point", "scope_id": scope_id, "knowledge_node_id": scope_id, "source_type": "model_generated"},
        )
        record = _update_saved_record(
            manager=manager, course_id=course_id, relative_path=relative_path,
            fields={
                "source_title": supplement.title, "source_language": "zh-CN", "content_language": "zh-CN",
                "authority_tier": "model_generated_reviewed", "generated_by": PLAN_BUILDER_VERSION,
                "generated_at": utc_now(), "generation_audit": {
                    **supplement.audit, **dict(fallback_audit or {}),
                    "build_id": str(topic.get("material_namespace") or ""),
                    "model": resolved.get("model"),
                    "prompt_version": "course-leaf-supplement-v1",
                },
                "generation_review_score": supplement.review_score, "doc_kind": "generated",
                "learning_artifacts": list(supplement.audit.get("learning_artifacts") or []),
                "source_type": "model_generated", "status": "received",
                "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
                "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "content_chars": len(body),
            },
        )
    return {
        "document_id": record["id"], "scope_id": scope_id, "source_url": "", "reused": False,
        "source_type": "model_generated", "review_score": supplement.review_score,
        "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "content_chars": len(body),
        "chunk_count": int(import_result.get("chunk_count") or 0),
        "fallback_audit": dict(fallback_audit or {}),
        "learning_artifacts": list(supplement.audit.get("learning_artifacts") or []),
    }


def parsed_domain(url: str) -> str:
    return str(urlparse(url).hostname or "")


def _ingest_online_textbook_candidate(
    candidate: Mapping[str, Any],
    *,
    pdf_parser: Any | None = None,
) -> dict[str, Any]:
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/2.0 (+source-attribution)"}
    with httpx.Client(timeout=60, follow_redirects=False, headers=headers) as client:
        fetched = fetch_source(
            client,
            candidate,
            robots_allowed=lambda url: _robots_allows(client, url),
        )
    parse_result = (
        parse_pdf_source(fetched, pdf_parser=pdf_parser)
        if fetched.content_format == "pdf"
        else parse_html_source(fetched)
    )
    linked_chapter_urls = [
        str(item).strip()
        for item in (candidate.get("metadata") or {}).get("linked_chapter_urls") or []
        if str(item).strip()
    ]
    if linked_chapter_urls:
        chapter_results: list[tuple[str, Mapping[str, Any]]] = []
        chapter_warnings: list[dict[str, str]] = []
        with httpx.Client(timeout=60, follow_redirects=False, headers=headers) as client:
            for chapter_url in linked_chapter_urls:
                chapter_candidate = {
                    "url": chapter_url,
                    "title": (
                        f"{candidate.get('title') or '在线教材'} · "
                        f"{chapter_url.rsplit('/', 1)[-1]}"
                    ),
                    "metadata": {"content_format_hint": "pdf"},
                }
                try:
                    chapter_fetched = fetch_source(
                        client,
                        chapter_candidate,
                        robots_allowed=lambda url: _robots_allows(client, url),
                    )
                    chapter_results.append(
                        (
                            chapter_fetched.final_url,
                            parse_pdf_source(chapter_fetched, pdf_parser=pdf_parser),
                        )
                    )
                except Exception as exc:
                    chapter_warnings.append(
                        {"source_url": chapter_url, "message": str(exc)}
                    )
        if not chapter_results:
            raise SourceIngestionError(
                "TEXTBOOK_CHAPTER_BUNDLE_FAILED",
                "在线教材章节目录可访问，但所有经审核的章节 PDF 均下载或解析失败",
            )
        merged_outline: list[dict[str, Any]] = []
        merged_chunks: list[dict[str, Any]] = []
        summaries: list[str] = []
        char_count = 0
        for chapter_url, result in chapter_results:
            summaries.append(str(result.get("summary") or ""))
            char_count += int(result.get("char_count") or 0)
            merged_outline.extend(dict(item) for item in result.get("outline") or [])
            merged_chunks.extend(
                {**dict(item), "source_url": chapter_url}
                for item in result.get("chunks") or []
            )
        parse_result = {
            "parser": "linked-pdf-bundle",
            "parser_metadata": {
                "catalog_url": fetched.final_url,
                "chapter_urls": [item[0] for item in chapter_results],
                "failed_chapters": chapter_warnings,
            },
            "summary": "\n\n".join(item for item in summaries if item)[:4000],
            "outline": merged_outline,
            "chunks": merged_chunks,
            "char_count": char_count,
            "chapter_count": len(merged_outline),
            "chunk_count": len(merged_chunks),
            "warnings": chapter_warnings,
            "parsed_at": utc_now(),
        }
    suffix = ".pdf" if fetched.content_format == "pdf" else ".html"
    textbook_id = f"online-{fetched.content_hash[:20]}"
    return {
        "textbook_id": textbook_id,
        "filename": _safe_material_filename(
            "online-textbook", fetched.title, fetched.final_url
        ).rsplit(".", 1)[0]
        + suffix,
        "status": "ready",
        "payload": fetched.payload,
        "content_hash": fetched.content_hash,
        "source_url": fetched.final_url,
        "original_url": fetched.original_url,
        "retrieved_at": fetched.retrieved_at,
        "content_format": fetched.content_format,
        "parse_result": parse_result,
        "source_candidate_id": candidate.get("candidate_id"),
        "source_domain": candidate.get("domain"),
        "authority_tier": candidate.get("authority_tier"),
        "is_online_textbook": True,
    }


def _reviewed_generated_documents(
    manager: CourseStorageManager,
    *,
    course_id: str,
    scope_id: str,
    limit: int,
    build_id: str = "",
) -> list[dict[str, Any]]:
    """Resume independently reviewed supplements from an interrupted build."""
    if limit <= 0 or not hasattr(manager, "get_knowledge_base_index"):
        return []
    eligible: list[dict[str, Any]] = []
    for record in reversed(manager.get_knowledge_base_index(course_id)):
        document_id = str(record.get("id") or "")
        if (
            not document_id
            or str(record.get("scope_id") or "") != scope_id
            or record.get("source_type") != "model_generated"
            or int(record.get("generation_review_score") or 0) < 80
            or str(record.get("status") or "received") not in {"received", "ready"}
            or (
                build_id
                and str((record.get("generation_audit") or {}).get("build_id") or "")
                != build_id
            )
        ):
            continue
        item = {
            "document_id": document_id,
            "scope_id": scope_id,
            "source_url": "",
            "reused": str(record.get("status") or "received") == "ready",
            "resumed": True,
            "source_type": "model_generated",
            "review_score": int(record.get("generation_review_score") or 0),
        }
        for field in ("content_hash", "content_chars", "chunk_count"):
            if record.get(field) is not None:
                item[field] = record[field]
        if record.get("generation_audit"):
            item["fallback_audit"] = dict(record["generation_audit"])
        if record.get("learning_artifacts"):
            item["learning_artifacts"] = [
                dict(artifact)
                for artifact in record.get("learning_artifacts") or []
                if isinstance(artifact, Mapping)
            ]
        eligible.append(item)
        if len(eligible) >= limit:
            break
    return eligible


def _persist_textbook_materials(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    build: Mapping[str, Any],
    mapping_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Persist one visible original and one hidden indexed document per leaf/textbook."""
    persisted: list[dict[str, Any]] = []
    course_root = manager.get_course_dir(course_id).resolve()
    existing_index = manager.get_knowledge_base_index(course_id)
    textbooks = {
        str(item.get("textbook_id") or ""): item
        for item in [
            *(build.get("textbooks") or []),
            *(build.get("online_textbooks") or []),
        ]
        if item.get("status") == "ready"
    }
    for textbook_id, textbook in textbooks.items():
        existing = next(
            (
                item for item in existing_index
                if item.get("source_type") == "textbook_original"
                and item.get("source_build_id") == build.get("build_id")
                and item.get("textbook_id") == textbook_id
            ),
            None,
        )
        if existing:
            persisted.append({"document_id": str(existing.get("id") or ""), "scope_id": "", "source_type": "textbook_original", "reused": True})
            continue
        is_online = bool(textbook.get("is_online_textbook"))
        if is_online:
            payload = bytes(textbook.get("payload") or b"")
            if not payload:
                raise FileNotFoundError(f"在线教材缓存不存在：{textbook.get('filename')}")
            suffix = ".pdf" if textbook.get("content_format") == "pdf" or payload.startswith(b"%PDF-") else ".html"
        else:
            source_path = (course_root / str(textbook.get("relative_path") or "")).resolve()
            source_path.relative_to(course_root)
            if not source_path.is_file():
                raise FileNotFoundError(f"教材原文件不存在：{textbook.get('filename')}")
            payload = source_path.read_bytes()
            suffix = source_path.suffix.lower()
        filename = f"kbbuild-textbook-{textbook_id}-{str(textbook.get('content_hash') or '')[:12]}{suffix}"
        relative_path = manager.save_knowledge_base_file(
            course_id, payload, filename,
            scope_type="course", scope_id=course_id, library_type=LIBRARY_TYPE_COURSE,
        )
        full_path = manager.get_course_dir(course_id) / relative_path
        if is_online:
            import_result = {
                "chunk_count": int((textbook.get("parse_result") or {}).get("chunk_count") or 0)
            }
        else:
            import_result = rag_system.import_document(
                str(full_path), force_reimport=True, owner=owner_user_id,
                metadata_overrides={
                    "course_id": course_id, "library_type": LIBRARY_TYPE_COURSE,
                    "scope_type": "course", "scope_id": course_id,
                    "source_type": "textbook_original", "source_build_id": build.get("build_id"),
                    "textbook_id": textbook_id,
                },
            )
        record = _update_saved_record(
            manager=manager, course_id=course_id, relative_path=relative_path,
            fields={
                "source_type": "textbook_original", "doc_kind": "textbook",
                    "source_build_id": build.get("build_id"), "textbook_id": textbook_id,
                    "content_hash": textbook.get("content_hash"), "status": "received",
                    "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
                    "source_url": textbook.get("source_url"),
                    "source_domain": textbook.get("source_domain"),
                    "authority_tier": textbook.get("authority_tier"),
                    "retrieved_at": textbook.get("retrieved_at"),
                    "is_online_textbook": is_online,
                    "parser_metadata": (textbook.get("parse_result") or {}).get("parser_metadata"),
                },
            )
        persisted.append({"document_id": record["id"], "scope_id": "", "source_type": "textbook_original", "reused": False})

    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for mapping in mapping_result.get("mappings") or []:
        key = (str(mapping.get("textbook_id") or ""), str(mapping.get("knowledge_node_id") or ""))
        if all(key):
            groups.setdefault(key, []).append(mapping)
    for (textbook_id, scope_id), mappings in groups.items():
        existing = next(
            (
                item for item in existing_index
                if item.get("source_type") == "textbook"
                and item.get("source_build_id") == build.get("build_id")
                and item.get("textbook_id") == textbook_id
                and str(item.get("scope_id") or "") == scope_id
            ),
            None,
        )
        if existing:
            persisted.append({
                "document_id": str(existing.get("id") or ""),
                "scope_id": scope_id,
                "source_type": "textbook",
                "reused": True,
                "source_url": existing.get("source_url"),
                "source_domain": existing.get("source_domain"),
                "authority_tier": existing.get("authority_tier"),
                "is_online_textbook": existing.get("is_online_textbook", False),
            })
            continue
        textbook = textbooks[textbook_id]
        sections = [
            f"## {('第 ' + str(item.get('page')) + ' 页') if item.get('page') else item.get('chapter_title') or '教材章节'}\n\n"
            f"来源：{item.get('source_url') or textbook.get('source_url') or ''}\n\n"
            f"{item.get('content') or ''}"
            for item in mappings
        ]
        body = f"# {textbook.get('filename')} · 节点资料\n\n" + "\n\n".join(sections)
        filename = _safe_material_filename("textbook-node", str(textbook.get("filename") or "教材"), f"{build.get('build_id')}:{textbook_id}:{scope_id}")
        relative_path = manager.save_knowledge_base_file(
            course_id, body.encode("utf-8"), filename,
            scope_type="knowledge_point", scope_id=scope_id, library_type=LIBRARY_TYPE_COURSE,
        )
        full_path = manager.get_course_dir(course_id) / relative_path
        minimum_confidence = min(float(item.get("mapping_confidence") or 0) for item in mappings)
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        content_chars = len(body)
        is_online = bool(textbook.get("is_online_textbook"))
        import_result = rag_system.import_document(
            str(full_path), force_reimport=True, owner=owner_user_id,
            metadata_overrides={
                "course_id": course_id, "library_type": LIBRARY_TYPE_COURSE,
                "scope_type": "knowledge_point", "scope_id": scope_id,
                "knowledge_node_id": scope_id, "source_type": "textbook",
                "source_build_id": build.get("build_id"), "textbook_id": textbook_id,
                "mapping_method": "outline_anchor_or_semantic", "mapping_confidence": minimum_confidence,
            },
        )
        record = _update_saved_record(
            manager=manager, course_id=course_id, relative_path=relative_path,
            fields={
                "source_type": "textbook", "doc_kind": "textbook_chunk_group",
                "source_build_id": build.get("build_id"), "textbook_id": textbook_id,
                "textbook_mappings": [dict(item) for item in mappings],
                "display_in_library": False, "status": "received",
                "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
                "content_hash": content_hash, "content_chars": content_chars,
                "mapping_confidence": minimum_confidence,
                "source_url": textbook.get("source_url"),
                "source_domain": textbook.get("source_domain"),
                "authority_tier": textbook.get("authority_tier"),
                "source_artifact_id": textbook_id,
                "is_online_textbook": is_online,
                "provenance_ok": bool(
                    content_hash and (textbook.get("source_url") or textbook_id)
                ),
            },
        )
        persisted.append({
            "document_id": record["id"], "scope_id": scope_id,
            "source_type": "textbook", "reused": False,
            "content_hash": content_hash, "content_chars": content_chars,
            "mapping_confidence": minimum_confidence,
            "source_url": textbook.get("source_url"),
            "source_domain": textbook.get("source_domain"),
            "authority_tier": textbook.get("authority_tier"),
            "source_artifact_id": textbook_id,
            "is_online_textbook": is_online,
            "provenance_ok": bool(content_hash and (textbook.get("source_url") or textbook_id)),
            "chunk_count": int(import_result.get("chunk_count") or 0),
        })
    return persisted


def _published_graph(build: Mapping[str, Any], persisted: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not build.get("graph_draft"):
        raise ValueError("知识图谱草案不存在，禁止使用硬编码结构发布")
    graph = copy.deepcopy(build["graph_draft"])
    documents_by_topic: dict[str, list[str]] = {}
    for item in persisted:
        doc_id = str(item.get("document_id") or "")
        if doc_id and doc_id not in documents_by_topic.setdefault(str(item.get("scope_id") or ""), []):
            documents_by_topic[str(item.get("scope_id") or "")].append(doc_id)

    node_count = 0
    def attach(node: dict[str, Any]) -> None:
        nonlocal node_count
        node_count += 1
        children = node.get("children") or []
        if not children and (node.get("data") or {}).get("type") == "knowledge_point":
            node.setdefault("data", {})["document_ids"] = list(dict.fromkeys([*node.get("data", {}).get("document_ids", []), *documents_by_topic.get(str(node.get("id") or ""), [])]))
        for child in children:
            attach(child)
    attach(graph)
    graph.setdefault("data", {}).update({
        "builder_version": PLAN_BUILDER_VERSION, "source_build_id": build.get("build_id"),
        "publication_status": "published", "node_count": node_count, "document_count": len(persisted),
    })
    return graph


def _validate_graph_and_coverage(graph: Mapping[str, Any]) -> tuple[bool, dict[str, int], list[str]]:
    seen: set[str] = set()
    coverage: dict[str, int] = {}
    issues: list[str] = []

    def visit(node: Mapping[str, Any], depth: int) -> None:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in seen:
            issues.append("知识图谱节点 ID 缺失或重复")
            return
        seen.add(node_id)
        children = list(node.get("children") or [])
        if not children:
            if depth < 2 or str((node.get("data") or {}).get("type") or "") != "knowledge_point":
                issues.append(f"叶节点 {node_id} 不是至少第三层的知识点")
            docs = {str(item) for item in (node.get("data") or {}).get("document_ids") or [] if str(item)}
            coverage[node_id] = len(docs)
            if len(docs) < MIN_DOCUMENTS_PER_LEAF:
                issues.append(f"叶节点 {node_id} 仅关联 {len(docs)} 份资料")
        for child in children:
            visit(child, depth + 1)

    visit(graph, 0)
    if not coverage:
        issues.append("知识图谱没有叶级知识点")
    return not issues, coverage, issues


def _textbook_first_coverage(
    topics: list[Mapping[str, Any]],
    persisted: list[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    return calculate_leaf_coverage(
        topics,
        persisted,
        target_units=max(1, int(config.get("target_materials_per_leaf") or 3)),
        minimum_external_sources=max(
            0, int(config.get("minimum_web_materials_per_leaf") or 0)
        ),
        maximum_ai=max(0, int(config.get("maximum_ai_materials_per_leaf") or 0)),
    )


def _missing_preferred_domains(
    topic: Mapping[str, Any], persisted: list[Mapping[str, Any]]
) -> list[str]:
    preferred = [
        str(item).casefold().strip(".")
        for item in dict(topic.get("source_policy") or {}).get("preferred_domains") or []
        if str(item).strip()
    ]
    if not preferred:
        return []
    topic_id = str(topic.get("topic_id") or "")
    present = {
        parsed_domain(str(item.get("final_url") or item.get("source_url") or ""))
        .casefold()
        .strip(".")
        for item in persisted
        if str(item.get("scope_id") or "") == topic_id
    }
    return [
        domain
        for domain in preferred
        if not any(host == domain or host.endswith("." + domain) for host in present)
    ]


def _candidate_fills_preferred_gap(
    candidate: Mapping[str, Any], missing_domains: list[str]
) -> bool:
    hostname = parsed_domain(str(candidate.get("url") or "")).casefold().strip(".")
    return any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in missing_domains
    )


def _run_textbook_first_build(
    *,
    repository: Any,
    build: dict[str, Any],
    job_id: str,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    progress: Callable[[int, str, str], None] | None,
) -> dict[str, Any]:
    config = _effective_build_config(build)
    topics = execution_topics(build)
    if not topics:
        raise ValueError("构建计划没有叶级知识点")
    persisted: list[dict[str, Any]] = list(build.get("existing_materials") or [])
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    all_candidates: list[dict[str, Any]] = []

    repository.update_build(build_id, status="running", phase="textbook_discovery", progress=3)
    if progress:
        progress(3, "textbook_discovery", "正在优先发现完整教材和课程讲义")
    textbook_discovery = discover_course_textbook_sources(build)
    all_candidates.extend(dict(item) for item in textbook_discovery["source_candidates"])
    warnings.extend(dict(item) for item in textbook_discovery["warnings"])
    build = repository.replace_build_source_candidates(
        build_id,
        topics=topics,
        candidates=all_candidates,
        warnings=warnings,
        discovery_metrics={"textbook": dict(textbook_discovery["metrics"])},
    )

    online_textbooks: list[dict[str, Any]] = []
    textbook_candidates = [
        item for item in all_candidates
        if item.get("selected") and item.get("review_status") == "relevant"
        and bool((item.get("metadata") or {}).get("institutional_authority"))
    ]
    for candidate in textbook_candidates:
        try:
            repository.update_build(
                build_id, status="running", phase="textbook_ingestion", progress=10
            )
            if progress:
                progress(10, "textbook_ingestion", f"正在下载并解析：{candidate.get('title')}")
            textbook = _ingest_online_textbook_candidate(candidate)
            online_textbooks.append(textbook)
            repository.update_source_candidate_result(
                build_id,
                str(candidate.get("candidate_id") or ""),
                review_status="ready",
                review_reason="教材下载和结构化解析成功",
                metadata={
                    "final_url": textbook.get("source_url"),
                    "content_hash": textbook.get("content_hash"),
                    "content_format": textbook.get("content_format"),
                    "parser": (textbook.get("parse_result") or {}).get("parser"),
                    "parser_metadata": (textbook.get("parse_result") or {}).get("parser_metadata"),
                    "parsed_at": (textbook.get("parse_result") or {}).get("parsed_at"),
                },
            )
            _update_candidate_in_memory(
                all_candidates,
                str(candidate.get("candidate_id") or ""),
                review_status="ready",
                review_reason="教材下载和结构化解析成功",
                metadata={
                    "final_url": textbook.get("source_url"),
                    "content_hash": textbook.get("content_hash"),
                },
            )
        except Exception as exc:
            code = exc.code if isinstance(exc, SourceIngestionError) else "TEXTBOOK_INGESTION_FAILED"
            failures.append({
                "code": code,
                "url": str(candidate.get("url") or ""),
                "topic_id": "",
                "error": str(exc),
            })
            repository.update_source_candidate_result(
                build_id,
                str(candidate.get("candidate_id") or ""),
                review_status="fetch_failed",
                review_reason=str(exc),
                metadata={"failure_code": code, "fetch_failed_at": utc_now()},
            )
            _update_candidate_in_memory(
                all_candidates,
                str(candidate.get("candidate_id") or ""),
                review_status="fetch_failed",
                review_reason=str(exc),
                metadata={"failure_code": code, "fetch_failed_at": utc_now()},
            )

    build = {**build, "online_textbooks": online_textbooks}
    mapping_result = map_textbook_chunks_to_graph(build)
    if online_textbooks or any(
        item.get("status") == "ready" for item in build.get("textbooks") or []
    ):
        repository.update_build(build_id, status="running", phase="textbook_mapping", progress=25)
        if progress:
            progress(25, "textbook_mapping", "正在将教材章节映射到已确认知识图谱")
        persisted.extend(
            _persist_textbook_materials(
                manager=manager,
                rag_system=rag_system,
                course_id=course_id,
                owner_user_id=owner_user_id,
                build={**build, "build_id": build_id},
                mapping_result=mapping_result,
            )
        )

    max_rounds = min(3, max(1, int(config.get("max_search_rounds_per_leaf") or 2)))
    seen_final_urls: set[str] = {str(d["final_url"]) for d in persisted if d.get("final_url")}
    seen_content_hashes: set[str] = {str(d["content_hash"]) for d in persisted if d.get("content_hash")}
    attempted_urls: set[str] = {
        canonical_source_url(item.get("source_url")) or str(item.get("source_url") or "")
        for item in online_textbooks
        if item.get("source_url")
    }
    topic_by_id = {str(item.get("topic_id") or ""): item for item in topics}
    leaf_search_rounds: dict[str, int] = {str(item["topic_id"]): 0 for item in topics}
    for round_index in range(max_rounds):
        coverage = _textbook_first_coverage(topics, persisted, config)
        gap_ids = {topic_id for topic_id, item in coverage.items() if item["unmet"]}
        # Exhaust every explicitly preferred domain before considering the
        # source search complete. This turns “Linux Kernel 与 Docker 官方”
        # into observable acquisition behavior instead of a label in metrics.
        gap_ids.update(
            str(topic.get("topic_id") or "")
            for topic in topics
            if _missing_preferred_domains(topic, persisted)
        )
        if not gap_ids:
            break
        discovery = discover_leaf_gap_sources(
            build, topic_ids=gap_ids, round_index=round_index
        )
        warnings.extend(dict(item) for item in discovery["warnings"])
        round_candidates = [dict(item) for item in discovery["source_candidates"]]
        all_candidates = _merge_source_candidates(all_candidates, round_candidates)
        active_candidate_ids = {
            str(item.get("candidate_id") or "") for item in all_candidates
        }
        round_candidates = [
            item
            for item in round_candidates
            if str(item.get("candidate_id") or "") in active_candidate_ids
        ]
        build = repository.replace_build_source_candidates(
            build_id,
            topics=topics,
            candidates=all_candidates,
            warnings=warnings,
            discovery_metrics={
                "textbook": dict(textbook_discovery["metrics"]),
                f"gap_round_{round_index + 1}": dict(discovery["metrics"]),
            },
        )
        build = {**build, "online_textbooks": online_textbooks}
        for topic_id in gap_ids:
            leaf_search_rounds[topic_id] = round_index + 1
        repository.update_build(
            build_id, status="running", phase="gap_search", progress=35 + round_index * 15
        )
        if progress:
            progress(
                35 + round_index * 15,
                "gap_search",
                f"正在执行第 {round_index + 1} 轮知识点缺口检索",
            )
        for candidate in round_candidates:
            if not candidate.get("selected") or candidate.get("review_status") != "relevant":
                continue
            topic_id = str(candidate.get("topic_id") or "")
            attempted_url = canonical_source_url(candidate.get("url")) or str(
                candidate.get("url") or ""
            )
            if attempted_url in attempted_urls:
                continue
            attempted_urls.add(attempted_url)
            current = _textbook_first_coverage(topics, persisted, config).get(topic_id, {})
            missing_preferred = _missing_preferred_domains(
                topic_by_id.get(topic_id, {}), persisted
            )
            fills_preferred_gap = _candidate_fills_preferred_gap(
                candidate, missing_preferred
            )
            if not current.get("unmet") and not fills_preferred_gap:
                continue
            try:
                item = _persist_candidate(
                    manager=manager,
                    rag_system=rag_system,
                    course_id=course_id,
                    owner_user_id=owner_user_id,
                    candidate=candidate,
                    seen_final_urls=seen_final_urls,
                    seen_content_hashes=seen_content_hashes,
                )
                item.setdefault("source_type", "web")
                item["provenance_ok"] = bool(
                    item.get("source_url") and item.get("content_hash")
                )
                persisted.append(item)
                repository.update_source_candidate_result(
                    build_id,
                    str(candidate.get("candidate_id") or ""),
                    review_status="ready",
                    review_reason="网页正文抓取、清洗与索引成功",
                    metadata={
                        "final_url": item.get("final_url"),
                        "content_hash": item.get("content_hash"),
                        "semantic_evidence_score": item.get("semantic_evidence_score"),
                        "fetched_at": utc_now(),
                    },
                )
                _update_candidate_in_memory(
                    all_candidates,
                    str(candidate.get("candidate_id") or ""),
                    review_status="ready",
                    review_reason="网页正文抓取、清洗与索引成功",
                    metadata={
                        "final_url": item.get("final_url"),
                        "content_hash": item.get("content_hash"),
                        "semantic_evidence_score": item.get("semantic_evidence_score"),
                        "fetched_at": utc_now(),
                    },
                )
            except Exception as exc:
                code = exc.code if isinstance(exc, SourceIngestionError) else "SOURCE_INGESTION_FAILED"
                failures.append({
                    "code": code,
                    "url": str(candidate.get("url") or ""),
                    "topic_id": topic_id,
                    "error": str(exc),
                })
                repository.update_source_candidate_result(
                    build_id,
                    str(candidate.get("candidate_id") or ""),
                    review_status="fetch_failed",
                    review_reason=str(exc),
                    metadata={"failure_code": code, "fetch_failed_at": utc_now()},
                )
                _update_candidate_in_memory(
                    all_candidates,
                    str(candidate.get("candidate_id") or ""),
                    review_status="fetch_failed",
                    review_reason=str(exc),
                    metadata={"failure_code": code, "fetch_failed_at": utc_now()},
                )

    fetch_failed_by_leaf: dict[str, int] = {}
    fetch_failed_by_code: dict[str, int] = {}
    for failure in failures:
        topic_id = str(failure.get("topic_id") or "")
        code = str(failure.get("code") or "UNKNOWN")
        if topic_id:
            fetch_failed_by_leaf[topic_id] = fetch_failed_by_leaf.get(topic_id, 0) + 1
        fetch_failed_by_code[code] = fetch_failed_by_code.get(code, 0) + 1
    build["metrics"] = {
        **dict(build.get("metrics") or {}),
        "fetch_failed_by_leaf": fetch_failed_by_leaf,
        "fetch_failed_by_code": fetch_failed_by_code,
        "leaf_search_rounds": leaf_search_rounds,
    }

    maximum_ai = max(0, int(config.get("maximum_ai_materials_per_leaf") or 0))
    ai_enabled = bool(config.get("ai_supplement_enabled", True))
    before_ai = _textbook_first_coverage(topics, persisted, config)
    deficits: list[tuple[Mapping[str, Any], int]] = []
    for topic in topics:
        topic_id = str(topic.get("topic_id") or "")
        missing_units = max(
            0,
            int(topic.get("target_units") or config.get("target_materials_per_leaf") or 3)
            - int(before_ai[topic_id]["effective_units"]),
        )
        ai_budget = min(maximum_ai, missing_units) if ai_enabled else 0
        resume_limit = _reviewed_generation_resume_limit(
            topic,
            ai_budget=ai_budget,
            ai_enabled=ai_enabled,
            maximum_ai=maximum_ai,
        )
        resumed = _reviewed_generated_documents(
            manager,
            course_id=course_id,
            scope_id=topic_id,
            limit=resume_limit,
            build_id=build_id,
        )
        persisted.extend(resumed)
        deficits.extend(
            (topic, sequence)
            for sequence in range(1, max(0, ai_budget - len(resumed)) + 1)
        )
    _ensure_required_artifact_generation(
        deficits,
        topics=topics,
        persisted=persisted,
        ai_enabled=ai_enabled,
        maximum_ai=maximum_ai,
    )

    course_title = str((build.get("course_snapshot") or {}).get("title") or "课程")
    persistence_lock = RLock()
    if deficits:
        repository.update_build(build_id, status="running", phase="ai_fallback", progress=72)
        if progress:
            progress(72, "ai_fallback", "非 AI 路径已耗尽，正在补充剩余内容缺口")
        with ThreadPoolExecutor(max_workers=min(3, len(deficits))) as pool:
            future_map = {
                pool.submit(
                    _generate_and_persist_supplement,
                    manager=manager,
                    rag_system=rag_system,
                    course_id=course_id,
                    owner_user_id=owner_user_id,
                    course_title=course_title,
                    topic=topic,
                    sequence=sequence,
                    persistence_lock=persistence_lock,
                    fallback_audit={
                        "fallback_reason": (
                            "teacher_required_artifact"
                            if topic.get("artifact_generation_only")
                            else "non_ai_search_exhausted"
                        ),
                        "non_ai_attempt_count": leaf_search_rounds[str(topic["topic_id"])],
                        "pre_ai_coverage": before_ai[str(topic["topic_id"])],
                    },
                ): topic
                for topic, sequence in deficits
            }
            for future in as_completed(future_map):
                topic = future_map[future]
                try:
                    persisted.append(future.result())
                except Exception as exc:
                    failures.append({
                        "code": "AI_SUPPLEMENT_FAILED",
                        "url": "",
                        "topic_id": str(topic.get("topic_id") or ""),
                        "error": str(exc),
                    })

    graph = _published_graph({**build, "build_id": build_id}, persisted)
    quality = evaluate_course_knowledge_quality(
        build,
        persisted,
        textbook_metrics=dict(mapping_result.get("metrics") or {}),
        index_integrity=all(str(item.get("document_id") or "") for item in persisted),
        publication_atomicity=True,
    )
    final_coverage = quality["leaf_coverage"]
    leaf_count = max(1, len(final_coverage))
    non_ai_covered = sum(
        item["textbook_units"] + item["web_units"]
        >= int(config.get("target_materials_per_leaf") or 3)
        for item in final_coverage.values()
    )
    ai_count = sum(item["ai_units"] for item in final_coverage.values())
    effective_count = sum(item["effective_units"] for item in final_coverage.values())
    quality_score = float(quality["quality_score"])
    quality_details = {
        **quality,
        "selected_source_count": sum(bool(item.get("selected")) for item in all_candidates),
        "persisted_document_count": len(persisted),
        "topic_count": len(topics),
        "failures": failures,
        "textbook_mapping": mapping_result.get("metrics") or {},
        "unmapped_textbook_chunks": mapping_result.get("unmapped") or [],
        "acquisition_order": ["textbook", "gap_web", "model_generated"],
        "textbook_candidates": len(textbook_candidates),
        "textbook_ingested": len(online_textbooks),
        "pdf_downloaded": sum(item.get("content_format") == "pdf" for item in online_textbooks),
        "mineru_parsed": sum((item.get("parse_result") or {}).get("parser") != "structured-html" for item in online_textbooks),
        "non_ai_coverage_rate": round(non_ai_covered / leaf_count, 4),
        "ai_material_ratio": round(ai_count / effective_count, 4) if effective_count else 0,
        "leaves_requiring_ai": sum(item["ai_units"] > 0 for item in final_coverage.values()),
        "fetch_failed_by_code": fetch_failed_by_code,
        "leaf_search_rounds": leaf_search_rounds,
    }
    for check in quality["checks"]:
        repository.record_quality_check(
            build_id,
            check_type=check["check_type"],
            status=check["status"],
            score=1 if check["status"] == "passed" else 0,
            threshold=1,
            details=check["details"],
        )
    repository.update_build(
        build_id, status="running", phase="quality_check", progress=85,
        metrics=quality_details, quality_score=quality_score,
    )
    if not quality["passed"]:
        failed_checks = [item["check_type"] for item in quality["checks"] if item["status"] != "passed"]
        repository.update_build(
            build_id, status="blocked", phase="quality_blocked", progress=100,
            metrics=quality_details, quality_score=quality_score,
            error={"code": "QUALITY_GATE_FAILED", "message": f"质量门禁未通过：{', '.join(failed_checks)}"},
        )
        raise RuntimeError(f"质量门禁未通过（{quality_score:.0f}/100）：{', '.join(failed_checks)}")
    repository.update_build(
        build_id, status="publishing", phase="publishing", progress=95,
        metrics=quality_details, quality_score=quality_score,
    )
    if progress:
        progress(95, "publishing", "质量门禁已通过，正在原子发布知识库")
    published_version = repository.publish_build(
        build_id,
        graph=graph,
        document_ids=[str(item.get("document_id") or "") for item in persisted if item.get("document_id")],
        metrics=quality_details,
        quality_score=quality_score,
    )
    result = {
        "resource_type": "course_knowledge_base", "course_id": course_id,
        "build_id": build_id, "document_count": len(persisted), "topic_count": len(topics),
        "quality_score": quality_score, "published_version": published_version,
        "warning_count": len(failures), "warnings": failures,
        "leaf_coverage": final_coverage, "published_at": utc_now(),
    }
    update_job(
        job_id, status=JobStatus.SUCCEEDED, step="completed", progress=100,
        message="课程知识库已通过质量检查并发布", result_ref=result,
    )
    return result


def run_course_knowledge_plan_build_job(
    *,
    job_id: str,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    progress: Callable[[int, str, str], None] | None = None,
    is_cancel_requested: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    repository = _knowledge_repository()
    build = repository.get_build(build_id)
    progress_reporter = progress

    def guarded_progress(value: int, step: str, message: str) -> None:
        if is_cancel_requested is not None and is_cancel_requested():
            raise CourseKnowledgeBuildCancelled("课程知识库构建已由用户取消")
        if progress_reporter is not None:
            progress_reporter(value, step, message)

    progress = guarded_progress if progress_reporter is not None or is_cancel_requested is not None else None
    try:
        if build is None or str(build.get("library_id") or "") != course_id:
            raise ValueError("知识库构建计划不存在")
        feature_enabled = os.getenv(
            "COURSE_KB_TEXTBOOK_FIRST_ENABLED", "true"
        ).strip().casefold() not in {"0", "false", "off", "no"}
        if feature_enabled and bool(
            dict(build.get("config") or {}).get("prefer_complete_textbooks", False)
        ):
            return _run_textbook_first_build(
                repository=repository,
                build=dict(build),
                job_id=job_id,
                manager=manager,
                rag_system=rag_system,
                course_id=course_id,
                owner_user_id=owner_user_id,
                build_id=build_id,
                progress=progress,
            )
        repository.update_build(build_id, status="running", phase="source_discovery", progress=3)
        if progress:
            progress(3, "source_discovery", "正在按已确认图谱逐个搜索网络资料")
        discovery = discover_course_knowledge_sources(build)
        build = repository.replace_build_source_candidates(
            build_id,
            topics=list(discovery["topics"]),
            candidates=list(discovery["source_candidates"]),
            warnings=list(discovery["warnings"]),
            discovery_metrics=dict(discovery["metrics"]),
        )
        selected = [
            item
            for item in build.get("source_candidates") or []
            if item.get("selected") and item.get("review_status") == "relevant"
        ]
        topics = list(build.get("topics") or [])
        if not topics:
            raise ValueError("构建计划没有叶级知识点")
        config = _effective_build_config(build)
        target_per_leaf = max(
            1, int(config.get("target_materials_per_leaf") or MIN_DOCUMENTS_PER_LEAF)
        )
        minimum_web_per_leaf = max(
            0, int(config.get("minimum_web_materials_per_leaf") or 0)
        )
        desired_web_per_leaf = max(target_per_leaf, minimum_web_per_leaf)
        repository.update_build(build_id, status="running", phase="source_audit", progress=5)
        if progress:
            progress(5, "source_audit", "正在抓取中文优先、配置语言补充的网页正文")
        persisted: list[dict[str, Any]] = list(build.get("existing_materials") or [])
        failures: list[dict[str, str]] = []
        total_steps = max(1, len(selected) + len(topics) * MIN_DOCUMENTS_PER_LEAF)
        completed_steps = 0
        web_success_by_leaf: dict[str, int] = {}
        seen_final_urls: set[str] = {str(d["final_url"]) for d in persisted if d.get("final_url")}
        seen_content_hashes: set[str] = {str(d["content_hash"]) for d in persisted if d.get("content_hash")}
        for candidate in selected:
            topic_id = str(candidate.get("topic_id") or "")
            if web_success_by_leaf.get(topic_id, 0) >= desired_web_per_leaf:
                completed_steps += 1
                build_progress = 10 + round(completed_steps / total_steps * 65)
                repository.update_build(
                    build_id,
                    status="running",
                    phase="indexing",
                    progress=build_progress,
                )
                if progress:
                    progress(
                        build_progress,
                        "indexing",
                        f"已处理 {completed_steps}/{len(selected)} 个网络来源",
                    )
                continue
            try:
                item = _persist_candidate(
                    manager=manager,
                    rag_system=rag_system,
                    course_id=course_id,
                    owner_user_id=owner_user_id,
                    candidate=candidate,
                    seen_final_urls=seen_final_urls,
                    seen_content_hashes=seen_content_hashes,
                )
                item.setdefault("source_type", "web")
                item["provenance_ok"] = bool(item.get("source_url") and item.get("content_hash"))
                persisted.append(item)
                web_success_by_leaf[topic_id] = web_success_by_leaf.get(topic_id, 0) + 1
                repository.update_source_candidate_result(
                    build_id,
                    str(candidate.get("candidate_id") or ""),
                    review_status="ready",
                    review_reason="网页正文抓取、清洗与索引成功",
                    metadata={
                        "final_url": item.get("final_url"),
                        "content_hash": item.get("content_hash"),
                        "fetched_at": utc_now(),
                    },
                )
            except Exception as exc:
                failures.append({"url": str(candidate.get("url") or ""), "topic_id": str(candidate.get("topic_id") or ""), "error": str(exc)})
                repository.update_source_candidate_result(
                    build_id,
                    str(candidate.get("candidate_id") or ""),
                    review_status="fetch_failed",
                    review_reason=str(exc),
                    metadata={"fetch_failed_at": utc_now()},
                )
            completed_steps += 1
            build_progress = 10 + round(completed_steps / total_steps * 65)
            repository.update_build(build_id, status="running", phase="indexing", progress=build_progress)
            if progress:
                progress(
                    build_progress,
                    "indexing",
                    f"已处理 {completed_steps}/{len(selected)} 个网络来源",
                )

        fetch_failed_by_leaf: dict[str, int] = {}
        for failure in failures:
            topic_id = str(failure.get("topic_id") or "")
            if topic_id:
                fetch_failed_by_leaf[topic_id] = fetch_failed_by_leaf.get(topic_id, 0) + 1
        build["metrics"] = {**dict(build.get("metrics") or {}), "fetch_failed_by_leaf": fetch_failed_by_leaf}

        mapping_result = map_textbook_chunks_to_graph(build)
        if any(item.get("status") == "ready" for item in build.get("textbooks") or []):
            repository.update_build(build_id, status="running", phase="textbook_mapping", progress=45)
            if progress:
                progress(45, "textbook_mapping", "正在按确认图谱拆分并索引教材")
            persisted.extend(
                _persist_textbook_materials(
                    manager=manager, rag_system=rag_system, course_id=course_id,
                    owner_user_id=owner_user_id, build={**build, "build_id": build_id},
                    mapping_result=mapping_result,
                )
            )

        maximum_ai = max(0, int(config.get("maximum_ai_materials_per_leaf") or 0))
        ai_enabled = bool(config.get("ai_supplement_enabled", True))
        course_title = str((build.get("course_snapshot") or {}).get("title") or "课程")
        deficits: list[tuple[Mapping[str, Any], int]] = []
        for topic in topics:
            topic_id = str(topic.get("topic_id") or "")
            existing_count = len({str(item.get("document_id") or "") for item in persisted if str(item.get("scope_id") or "") == topic_id and item.get("document_id")})
            ai_budget = min(maximum_ai, max(0, int(topic.get("target_units") or target_per_leaf) - existing_count)) if ai_enabled else 0
            resumed = _reviewed_generated_documents(
                manager,
                course_id=course_id,
                scope_id=topic_id,
                limit=ai_budget,
                build_id=build_id,
            )
            persisted.extend(resumed)
            remaining = max(0, ai_budget - len(resumed))
            deficits.extend((topic, sequence) for sequence in range(1, remaining + 1))

        _ensure_required_artifact_generation(
            deficits,
            topics=topics,
            persisted=persisted,
            ai_enabled=ai_enabled,
            maximum_ai=maximum_ai,
        )

        persistence_lock = RLock()
        if deficits:
            with ThreadPoolExecutor(max_workers=min(3, len(deficits))) as pool:
                future_map = {
                    pool.submit(
                        _generate_and_persist_supplement,
                        manager=manager, rag_system=rag_system, course_id=course_id,
                        owner_user_id=owner_user_id, course_title=course_title,
                        topic=topic, sequence=sequence, persistence_lock=persistence_lock,
                    ): (topic, sequence)
                    for topic, sequence in deficits
                }
                for future in as_completed(future_map):
                    topic, _sequence = future_map[future]
                    topic_id = str(topic.get("topic_id") or "")
                    try:
                        persisted.append(future.result())
                    except Exception as exc:
                        failures.append({"url": "", "topic_id": topic_id, "error": str(exc)})
                    completed_steps += 1
                    build_progress = min(80, 10 + round(completed_steps / total_steps * 65))
                    repository.update_build(build_id, status="running", phase="model_fallback", progress=build_progress)
                    if progress:
                        progress(build_progress, "model_fallback", f"正在检查“{topic.get('title')}”的资料覆盖")

        graph = _published_graph({**build, "build_id": build_id}, persisted)
        quality = evaluate_course_knowledge_quality(
            build,
            persisted,
            textbook_metrics=dict(mapping_result.get("metrics") or {}),
            index_integrity=all(str(item.get("document_id") or "") for item in persisted),
            publication_atomicity=True,
        )
        quality_score = float(quality["quality_score"])
        quality_details = {
            **quality,
            "selected_source_count": len(selected),
            "persisted_document_count": len(persisted),
            "topic_count": len(topics),
            "failures": failures,
            "textbook_mapping": mapping_result.get("metrics") or {},
            "unmapped_textbook_chunks": mapping_result.get("unmapped") or [],
            "acquisition_order": ["web", "textbook", "model_generated"],
        }
        for check in quality["checks"]:
            repository.record_quality_check(
                build_id,
                check_type=check["check_type"],
                status=check["status"],
                score=1 if check["status"] == "passed" else 0,
                threshold=1,
                details=check["details"],
            )
        repository.update_build(build_id, status="running", phase="quality_check", progress=85, metrics=quality_details, quality_score=quality_score)
        if progress:
            progress(85, "quality_check", f"质量评分 {quality_score:.0f}/100")
        if not quality["passed"]:
            failed_checks = [item["check_type"] for item in quality["checks"] if item["status"] != "passed"]
            repository.update_build(build_id, status="blocked", phase="quality_blocked", progress=100, metrics=quality_details, quality_score=quality_score, error={"code": "QUALITY_GATE_FAILED", "message": f"质量门禁未通过：{', '.join(failed_checks)}"})
            raise RuntimeError(f"质量门禁未通过（{quality_score:.0f}/100）：{', '.join(failed_checks)}")

        repository.update_build(build_id, status="publishing", phase="publishing", progress=95, metrics=quality_details, quality_score=quality_score)
        published_version = repository.publish_build(
            build_id, graph=graph,
            document_ids=[str(item.get("document_id") or "") for item in persisted if item.get("document_id")],
            metrics=quality_details, quality_score=quality_score,
        )
        result = {
            "resource_type": "course_knowledge_base", "course_id": course_id, "build_id": build_id,
            "document_count": len(persisted), "topic_count": len(topics), "quality_score": quality_score,
            "published_version": published_version, "warning_count": len(failures), "warnings": failures,
            "leaf_coverage": quality["leaf_coverage"], "published_at": utc_now(),
        }
        update_job(job_id, status=JobStatus.SUCCEEDED, step="completed", progress=100, message="课程知识库已通过质量检查并发布", result_ref=result)
        return result
    except CourseKnowledgeBuildCancelled:
        current = repository.get_build(build_id)
        if current is not None and current.get("status") not in {"succeeded", "blocked"}:
            repository.update_build(
                build_id,
                status="canceled",
                phase="canceled",
                progress=int(current.get("progress") or 0),
                error={"code": "GENERATION_CANCELLED", "message": "课程知识库构建已取消"},
            )
        return {
            "resource_type": "course_knowledge_base",
            "course_id": course_id,
            "build_id": build_id,
            "canceled": True,
        }
    except Exception as exc:
        current = repository.get_build(build_id)
        if current is not None and current.get("status") != "blocked":
            repository.update_build(build_id, status="failed", phase="failed", progress=100, error={"code": "COURSE_KB_PLAN_BUILD_FAILED", "message": str(exc)})
        update_job(job_id, status=JobStatus.FAILED, step="failed", progress=100, message="课程知识库构建失败", error_code="COURSE_KB_PLAN_BUILD_FAILED", error_message=str(exc))
        raise
