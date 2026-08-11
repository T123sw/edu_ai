"""Build and publish a quality-gated course knowledge graph from a semantic plan."""

from __future__ import annotations

import copy
import re
from contextlib import nullcontext
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.persistence.dependencies import get_postgres_knowledge_repository
from app.services.course_generated_material import generate_reviewed_supplement
from app.services.course_knowledge_builder import _canonical_path, _robots_allows, _safe_material_filename, utc_now
from app.services.job_store import EduJob, JobKind, JobStatus, create_job, update_job
from core.course_storage import LIBRARY_TYPE_COURSE, CourseStorageManager


PLAN_BUILDER_VERSION = "course-kb-plan-v2"
MIN_DOCUMENTS_PER_LEAF = 3


def submit_course_knowledge_plan_build_job(*, course_id: str, owner_user_id: str, build_id: str) -> EduJob:
    repository = get_postgres_knowledge_repository()
    build = repository.get_build(build_id)
    if build is None or str(build.get("library_id") or "") != course_id:
        raise ValueError("知识库构建计划不存在")
    selected = [item for item in build.get("source_candidates") or [] if item.get("selected") and item.get("review_status") == "approved"]
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
    return title, content[:60000]


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


def _persist_candidate(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    url = str(candidate.get("url") or "").strip()
    scope_id = str(candidate.get("topic_id") or "")
    for existing in manager.get_knowledge_base_index(course_id):
        if (
            str(existing.get("source_url") or existing.get("url") or "").strip() == url
            and str(existing.get("scope_id") or "") == scope_id
            and existing.get("status") == "ready"
        ):
            return {"document_id": str(existing.get("id") or ""), "scope_id": scope_id, "source_url": url, "reused": True, "source_type": "web"}
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/2.0 (+source-attribution)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        title, content = _extract_reviewed_page(client, candidate)
    license_name = str(candidate.get("license_name") or "")
    license_url = str(candidate.get("license_url") or "")
    filename = _safe_material_filename("plan", title, f"{scope_id}:{url}")
    body = (
        f"# {title}\n\n> 来源：[{candidate.get('domain') or url}]({url})  \n"
        f"> 许可：[{license_name}]({license_url})  \n> 获取时间：{utc_now()}  \n"
        f"> 来源审核：{candidate.get('review_reason') or '已通过'}\n\n{content}\n"
    )
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
            "url": url, "source_url": url, "source_title": title,
            "source_domain": str(candidate.get("domain") or parsed_domain(url)),
            "source_site_name": str(candidate.get("domain") or parsed_domain(url)),
            "source_license": license_name, "source_license_url": license_url,
            "source_language": candidate.get("language"), "content_language": candidate.get("language"),
            "translation_notice": "原文入库，未经机器翻译", "authority_tier": candidate.get("authority_tier"),
            "generated_by": PLAN_BUILDER_VERSION, "retrieved_at": utc_now(), "doc_kind": "web",
            "source_type": "web", "status": "received", "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
        },
    )
    return {"document_id": record["id"], "scope_id": scope_id, "source_url": url, "reused": False, "source_type": "web"}


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
    }
    supplement = generate_reviewed_supplement(
        course_title=course_title,
        leaf_title=leaf_title,
        sequence=sequence,
        call_model=lambda prompt: str(rag_system._call_llm(prompt, llm_config=llm_config)),
    )
    filename = _safe_material_filename("generated", supplement.title, f"{course_id}:{scope_id}:{sequence}")
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
                "generated_at": utc_now(), "generation_audit": {**supplement.audit, "model": resolved.get("model"), "prompt_version": "course-leaf-supplement-v1"},
                "generation_review_score": supplement.review_score, "doc_kind": "generated",
                "source_type": "model_generated", "status": "received",
                "chunk_count": int(import_result.get("chunk_count") or 0), "indexed_at": utc_now(),
            },
        )
    return {
        "document_id": record["id"], "scope_id": scope_id, "source_url": "", "reused": False,
        "source_type": "model_generated", "review_score": supplement.review_score,
    }


def parsed_domain(url: str) -> str:
    return str(urlparse(url).hostname or "")


def _reviewed_generated_documents(
    manager: CourseStorageManager,
    *,
    course_id: str,
    scope_id: str,
    limit: int,
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
        ):
            continue
        eligible.append(
            {
                "document_id": document_id,
                "scope_id": scope_id,
                "source_url": "",
                "reused": str(record.get("status") or "received") == "ready",
                "resumed": True,
                "source_type": "model_generated",
                "review_score": int(record.get("generation_review_score") or 0),
            }
        )
        if len(eligible) >= limit:
            break
    return eligible


def _fallback_graph(build: Mapping[str, Any]) -> dict[str, Any]:
    topics = list(build.get("topics") or [])
    title = str((build.get("course_snapshot") or {}).get("title") or "课程")
    module_label = re.sub(r"(?:入门|基础|教程|课程)$", "", title).strip() or f"{title}核心知识"
    return {
        "id": "root", "label": f"{title}课程知识图谱",
        "children": [{
            "id": "module-core", "label": module_label,
            "children": [{
                "id": str(topic.get("topic_id") or ""), "label": str(topic.get("title") or "知识点"), "children": [],
                "data": {"level": 2, "type": "knowledge_point", "summary": str(topic.get("objective") or ""), "hasChildren": False, "document_ids": []},
            } for topic in topics],
            "data": {"level": 1, "type": "knowledge_module", "summary": f"{title}的核心概念与技能结构", "hasChildren": bool(topics)},
        }],
        "data": {"level": 0, "type": "course", "summary": "依据课程目标构建", "hasChildren": bool(topics)},
    }


def _published_graph(build: Mapping[str, Any], persisted: list[Mapping[str, Any]]) -> dict[str, Any]:
    graph = copy.deepcopy(build.get("graph_draft") or _fallback_graph(build))
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
            node.setdefault("data", {})["document_ids"] = documents_by_topic.get(str(node.get("id") or ""), [])
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
        selected = [item for item in build.get("source_candidates") or [] if item.get("selected") and item.get("review_status") == "approved"]
        topics = list(build.get("topics") or [])
        if not topics:
            raise ValueError("构建计划没有叶级知识点")
        repository.update_build(build_id, status="running", phase="source_audit", progress=5)
        if progress:
            progress(5, "source_audit", "正在核验中文优先、英文补充的来源")
        persisted: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        total_steps = max(1, len(selected) + len(topics) * MIN_DOCUMENTS_PER_LEAF)
        completed_steps = 0
        for candidate in selected:
            try:
                item = _persist_candidate(manager=manager, rag_system=rag_system, course_id=course_id, owner_user_id=owner_user_id, candidate=candidate)
                item.setdefault("source_type", "web")
                item["provenance_ok"] = bool(candidate.get("license_name") and candidate.get("license_url"))
                persisted.append(item)
            except Exception as exc:
                failures.append({"url": str(candidate.get("url") or ""), "topic_id": str(candidate.get("topic_id") or ""), "error": str(exc)})
            completed_steps += 1
            build_progress = 10 + round(completed_steps / total_steps * 65)
            repository.update_build(build_id, status="running", phase="indexing", progress=build_progress)

        course_title = str((build.get("course_snapshot") or {}).get("title") or "课程")
        deficits: list[tuple[Mapping[str, Any], int]] = []
        for topic in topics:
            topic_id = str(topic.get("topic_id") or "")
            existing_count = len({str(item.get("document_id") or "") for item in persisted if str(item.get("scope_id") or "") == topic_id and item.get("document_id")})
            resumed = _reviewed_generated_documents(
                manager,
                course_id=course_id,
                scope_id=topic_id,
                limit=max(0, MIN_DOCUMENTS_PER_LEAF - existing_count),
            )
            persisted.extend(resumed)
            remaining = max(0, MIN_DOCUMENTS_PER_LEAF - existing_count - len(resumed))
            deficits.extend((topic, sequence) for sequence in range(1, remaining + 1))

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
        hard_gate_passed, leaf_coverage, graph_issues = _validate_graph_and_coverage(graph)
        generated_items = [item for item in persisted if item.get("source_type") == "model_generated"]
        provenance_ok = all(item.get("source_type") == "model_generated" or item.get("provenance_ok", True) for item in persisted)
        generated_review_ok = all(int(item.get("review_score") or 0) >= 80 for item in generated_items)
        graph_score = 20.0 if not graph_issues or all("资料" in issue for issue in graph_issues) else 0.0
        coverage_score = 50.0 if all(count >= MIN_DOCUMENTS_PER_LEAF for count in leaf_coverage.values()) and leaf_coverage else 0.0
        ingestion_score = 15.0 if len(persisted) >= len(topics) * MIN_DOCUMENTS_PER_LEAF else 0.0
        provenance_score = 15.0 if provenance_ok and generated_review_ok else 0.0
        quality_score = round(graph_score + coverage_score + ingestion_score + provenance_score, 2)
        quality_details = {
            "selected_source_count": len(selected), "persisted_document_count": len(persisted),
            "topic_count": len(topics), "leaf_coverage": leaf_coverage,
            "minimum_documents_per_leaf": MIN_DOCUMENTS_PER_LEAF,
            "generated_document_count": len(generated_items), "generated_review_ok": generated_review_ok,
            "acquisition_order": ["chinese", "english_fallback", "model_generated"],
            "failures": failures, "graph_issues": graph_issues,
        }
        checks = [
            ("graph_structure", graph_score == 20, graph_score, 20),
            ("source_provenance", provenance_score == 15, provenance_score, 15),
            ("ingestion_success", ingestion_score == 15, ingestion_score, 15),
            ("leaf_document_coverage", coverage_score == 50, coverage_score, 50),
        ]
        for check_type, passed, score, threshold in checks:
            repository.record_quality_check(build_id, check_type=check_type, status="passed" if passed else "failed", score=score, threshold=threshold, details=quality_details)
        repository.update_build(build_id, status="running", phase="quality_check", progress=85, metrics=quality_details, quality_score=quality_score)
        if progress:
            progress(85, "quality_check", f"质量评分 {quality_score:.0f}/100")
        if not hard_gate_passed or quality_score < 80:
            repository.update_build(build_id, status="blocked", phase="quality_blocked", progress=100, metrics=quality_details, quality_score=quality_score, error={"code": "QUALITY_GATE_FAILED", "message": "叶级知识点资料覆盖或图谱结构未通过质量门禁"})
            raise RuntimeError(f"质量门禁未通过（{quality_score:.0f}/100）：{'；'.join(graph_issues)}")

        repository.update_build(build_id, status="publishing", phase="publishing", progress=95, metrics=quality_details, quality_score=quality_score)
        published_version = repository.publish_build(
            build_id, graph=graph,
            document_ids=[str(item.get("document_id") or "") for item in persisted if not item.get("reused")],
            metrics=quality_details, quality_score=quality_score,
        )
        result = {
            "resource_type": "course_knowledge_base", "course_id": course_id, "build_id": build_id,
            "document_count": len(persisted), "topic_count": len(topics), "quality_score": quality_score,
            "published_version": published_version, "warning_count": len(failures), "warnings": failures,
            "leaf_coverage": leaf_coverage, "published_at": utc_now(),
        }
        update_job(job_id, status=JobStatus.SUCCEEDED, step="completed", progress=100, message="课程知识库已通过质量检查并发布", result_ref=result)
        return result
    except Exception as exc:
        current = repository.get_build(build_id)
        if current is not None and current.get("status") != "blocked":
            repository.update_build(build_id, status="failed", phase="failed", progress=100, error={"code": "COURSE_KB_PLAN_BUILD_FAILED", "message": str(exc)})
        update_job(job_id, status=JobStatus.FAILED, step="failed", progress=100, message="课程知识库构建失败", error_code="COURSE_KB_PLAN_BUILD_FAILED", error_message=str(exc))
        raise
