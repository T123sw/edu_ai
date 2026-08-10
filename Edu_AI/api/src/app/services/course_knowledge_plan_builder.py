"""Build and publish a course knowledge graph from a reviewed semantic plan."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.persistence.dependencies import get_postgres_knowledge_repository
from app.services.course_knowledge_builder import (
    _canonical_path,
    _robots_allows,
    _safe_material_filename,
    utc_now,
)
from app.services.job_store import EduJob, JobKind, JobStatus, create_job, update_job
from core.course_storage import LIBRARY_TYPE_COURSE, CourseStorageManager


PLAN_BUILDER_VERSION = "course-kb-plan-v1"


def submit_course_knowledge_plan_build_job(
    *,
    course_id: str,
    owner_user_id: str,
    build_id: str,
) -> EduJob:
    repository = get_postgres_knowledge_repository()
    build = repository.get_build(build_id)
    if build is None or str(build.get("library_id") or "") != course_id:
        raise ValueError("知识库构建计划不存在")
    selected = [
        item
        for item in build.get("source_candidates") or []
        if item.get("selected") and item.get("review_status") == "approved"
    ]
    if not selected:
        raise ValueError("没有通过许可与相关性审核的来源，无法开始构建")
    from app.services.platform_task_handlers import enqueue_platform_task
    from app.services.runtime_config_resolver import runtime_config_resolver

    repository.queue_build(build_id, selected_source_count=len(selected))
    try:
        job = create_job(
            kind=JobKind.BUILD_KNOWLEDGE_INDEX,
            owner_user_id=owner_user_id,
            course_id=course_id,
            input_summary={"build_id": build_id, "selected_source_count": len(selected)},
        )
        queued_job = enqueue_platform_task(
            job=job,
            workflow_type="course_knowledge_plan_build",
            command={"course_id": course_id, "build_id": build_id},
            runtime_config_snapshot=runtime_config_resolver.capture_snapshot(owner_user_id),
        )
        if queued_job.status == JobStatus.FAILED:
            repository.update_build(
                build_id,
                status="failed",
                phase="enqueue_failed",
                progress=100,
                error={"code": "BUILD_ENQUEUE_FAILED", "message": queued_job.error_message or "任务入队失败"},
            )
        return queued_job
    except Exception as exc:
        repository.update_build(
            build_id,
            status="failed",
            phase="enqueue_failed",
            progress=100,
            error={"code": "BUILD_ENQUEUE_FAILED", "message": str(exc)},
        )
        raise


def _extract_reviewed_page(client: httpx.Client, candidate: Mapping[str, Any]) -> tuple[str, str]:
    url = str(candidate.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("来源必须使用 HTTPS")
    if candidate.get("review_status") != "approved":
        raise ValueError("来源尚未通过审核")
    if not candidate.get("license_name") or not candidate.get("license_url"):
        raise ValueError("来源缺少可验证的许可信息")
    if not _robots_allows(client, url):
        raise PermissionError("来源 robots.txt 不允许抓取")
    response = client.get(url)
    response.raise_for_status()
    if "html" not in str(response.headers.get("content-type") or "").casefold():
        raise ValueError("来源不是可解析的网页正文")
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup.select("script, style, nav, header, footer, aside, form, noscript"):
        element.decompose()
    main = soup.select_one("main, article, [role='main'], .md-content, #content") or soup.body
    if main is None:
        raise ValueError("来源页面没有可识别的正文")
    title = str(candidate.get("title") or (soup.title.string if soup.title and soup.title.string else url)).strip()
    lines = [re.sub(r"\s+", " ", value).strip() for value in main.get_text("\n").splitlines()]
    content = "\n\n".join(value for value in lines if value)
    if len(content) < 300:
        raise ValueError("来源正文过短")
    return title, content[:60000]


def _persist_candidate(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    url = str(candidate.get("url") or "").strip()
    for existing in manager.get_knowledge_base_index(course_id):
        if str(existing.get("source_url") or existing.get("url") or "").strip() == url and existing.get("status") == "ready":
            return {
                "document_id": str(existing.get("id") or ""),
                "scope_id": str(existing.get("scope_id") or candidate.get("topic_id") or ""),
                "source_url": url,
                "reused": True,
            }
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        title, content = _extract_reviewed_page(client, candidate)
    license_name = str(candidate.get("license_name") or "")
    license_url = str(candidate.get("license_url") or "")
    filename = _safe_material_filename("plan", title, url)
    body = (
        f"# {title}\n\n"
        f"> 来源：[{candidate.get('domain') or url}]({url})  \n"
        f"> 许可：[{license_name}]({license_url})  \n"
        f"> 获取时间：{utc_now()}  \n"
        f"> 来源审核：{candidate.get('review_reason') or '已通过'}\n\n"
        f"{content}\n"
    )
    scope_id = str(candidate.get("topic_id") or "")
    relative_path = manager.save_knowledge_base_file(
        course_id,
        body.encode("utf-8"),
        filename,
        scope_type="knowledge_point",
        scope_id=scope_id,
        library_type=LIBRARY_TYPE_COURSE,
    )
    if not relative_path:
        raise OSError("保存课程来源失败")
    full_path = manager.get_course_dir(course_id) / relative_path
    import_result = rag_system.import_document(
        str(full_path),
        force_reimport=True,
        owner=owner_user_id,
        metadata_overrides={
            "course_id": course_id,
            "library_type": LIBRARY_TYPE_COURSE,
            "scope_type": "knowledge_point",
            "scope_id": scope_id,
            "knowledge_node_id": scope_id,
        },
    )
    index = manager.get_knowledge_base_index(course_id)
    record = next(
        item for item in reversed(index)
        if _canonical_path(item.get("path")) == _canonical_path(relative_path)
    )
    record.update(
        {
            "url": url,
            "source_url": url,
            "source_title": title,
            "source_domain": str(candidate.get("domain") or parsed_domain(url)),
            "source_site_name": str(candidate.get("domain") or parsed_domain(url)),
            "source_license": license_name,
            "source_license_url": license_url,
            "source_language": candidate.get("language"),
            "content_language": candidate.get("language"),
            "translation_notice": "原文入库，未经过机器翻译",
            "authority_tier": candidate.get("authority_tier"),
            "generated_by": PLAN_BUILDER_VERSION,
            "retrieved_at": utc_now(),
            "doc_kind": "web",
            "status": "received",
            "chunk_count": int(import_result.get("chunk_count") or 0),
            "indexed_at": utc_now(),
        }
    )
    manager.save_knowledge_base_index(course_id, index)
    return {"document_id": record["id"], "scope_id": scope_id, "source_url": url, "reused": False}


def parsed_domain(url: str) -> str:
    return str(urlparse(url).hostname or "")


def _published_graph(build: Mapping[str, Any], persisted: list[Mapping[str, Any]]) -> dict[str, Any]:
    documents_by_topic: dict[str, list[str]] = {}
    for item in persisted:
        documents_by_topic.setdefault(str(item.get("scope_id") or ""), []).append(str(item.get("document_id") or ""))
    topics = list(build.get("topics") or [])
    title = str((build.get("course_snapshot") or {}).get("title") or "课程")
    children = [
        {
            "id": str(topic.get("topic_id") or ""),
            "label": str(topic.get("title") or "知识主题"),
            "children": [],
            "data": {
                "level": 1,
                "type": "knowledge_point",
                "summary": str(topic.get("objective") or ""),
                "hasChildren": False,
                "document_ids": documents_by_topic.get(str(topic.get("topic_id") or ""), []),
            },
        }
        for topic in topics
    ]
    return {
        "id": "root",
        "label": f"{title}课程知识图谱",
        "children": children,
        "data": {
            "level": 0,
            "type": "course",
            "summary": "依据课程目标与通过许可审核的来源构建。",
            "hasChildren": bool(children),
            "builder_version": PLAN_BUILDER_VERSION,
            "source_build_id": build.get("build_id"),
            "publication_status": "published",
            "node_count": 1 + len(children),
            "document_count": len(persisted),
        },
    }


def run_course_knowledge_plan_build_job(
    *,
    job_id: str,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, Any]:
    repository = get_postgres_knowledge_repository()
    build = repository.get_build(build_id)
    try:
        if build is None or str(build.get("library_id") or "") != course_id:
            raise ValueError("知识库构建计划不存在")
        selected = [
            item for item in build.get("source_candidates") or []
            if item.get("selected") and item.get("review_status") == "approved"
        ]
        if not selected:
            raise ValueError("没有通过审核的来源")
        repository.update_build(build_id, status="running", phase="source_audit", progress=5)
        if progress:
            progress(5, "source_audit", "正在核验来源许可与抓取约束")
        persisted: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for index, candidate in enumerate(selected, start=1):
            try:
                persisted.append(
                    _persist_candidate(
                        manager=manager,
                        rag_system=rag_system,
                        course_id=course_id,
                        owner_user_id=owner_user_id,
                        candidate=candidate,
                    )
                )
            except Exception as exc:
                failures.append({"url": str(candidate.get("url") or ""), "error": str(exc)})
            build_progress = 10 + round(index / len(selected) * 65)
            repository.update_build(build_id, status="running", phase="indexing", progress=build_progress)
            if progress:
                progress(build_progress, "indexing", f"正在处理审核来源 {index}/{len(selected)}")

        topics = list(build.get("topics") or [])
        covered_topics = {str(item.get("scope_id") or "") for item in persisted}
        provenance_score = 30.0 if all(item.get("license_name") and item.get("license_url") for item in selected) else 0.0
        ingestion_score = 40.0 * len(persisted) / len(selected)
        coverage_score = 30.0 * len(covered_topics) / max(1, len(topics))
        quality_score = round(provenance_score + ingestion_score + coverage_score, 2)
        quality_details = {
            "selected_source_count": len(selected),
            "persisted_document_count": len(persisted),
            "topic_count": len(topics),
            "covered_topic_count": len(covered_topics),
            "failures": failures,
        }
        repository.record_quality_check(build_id, check_type="source_provenance", status="passed" if provenance_score == 30 else "failed", score=provenance_score, threshold=30, details=quality_details)
        repository.record_quality_check(build_id, check_type="ingestion_success", status="passed" if persisted else "failed", score=ingestion_score, threshold=1, details=quality_details)
        repository.record_quality_check(build_id, check_type="topic_coverage", status="passed" if coverage_score >= 15 else "failed", score=coverage_score, threshold=15, details=quality_details)
        repository.update_build(build_id, status="running", phase="quality_check", progress=85, metrics=quality_details, quality_score=quality_score)
        if progress:
            progress(85, "quality_check", f"质量评分 {quality_score:.0f}/100")
        if quality_score < 70 or ingestion_score <= 0 or coverage_score < 15:
            repository.update_build(build_id, status="blocked", phase="quality_blocked", progress=100, metrics=quality_details, quality_score=quality_score, error={"code": "QUALITY_GATE_FAILED", "message": "质量门禁未通过"})
            raise RuntimeError(f"质量门禁未通过（{quality_score:.0f}/100）")

        graph = _published_graph(build, persisted)
        repository.update_build(build_id, status="publishing", phase="publishing", progress=95, metrics=quality_details, quality_score=quality_score)
        published_version = repository.publish_build(
            build_id,
            graph=graph,
            document_ids=[str(item.get("document_id") or "") for item in persisted if not item.get("reused")],
            metrics=quality_details,
            quality_score=quality_score,
        )
        result = {
            "resource_type": "course_knowledge_base",
            "course_id": course_id,
            "build_id": build_id,
            "document_count": len(persisted),
            "topic_count": len(topics),
            "quality_score": quality_score,
            "published_version": published_version,
            "warning_count": len(failures),
            "warnings": failures,
            "published_at": utc_now(),
        }
        update_job(job_id, status=JobStatus.SUCCEEDED, step="completed", progress=100, message="课程知识库已通过质量检查并发布", result_ref=result)
        return result
    except Exception as exc:
        current = repository.get_build(build_id)
        if current is not None and current.get("status") != "blocked":
            repository.update_build(build_id, status="failed", phase="failed", progress=100, error={"code": "COURSE_KB_PLAN_BUILD_FAILED", "message": str(exc)})
        update_job(job_id, status=JobStatus.FAILED, step="failed", progress=100, message="课程知识库构建失败", error_code="COURSE_KB_PLAN_BUILD_FAILED", error_message=str(exc))
        raise
