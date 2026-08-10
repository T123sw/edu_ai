"""Lifecycle service for course knowledge documents and their RAG indexes."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.services.job_store import (
    ACTIVE_JOB_STATUSES,
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    update_job,
)
from modules.rag_v2.document_resolver import resolve_rag_document

_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _can_access(record: dict[str, Any], owner_user_id: str) -> bool:
    if str(record.get("library_type") or "course") != "personal":
        return True
    return str(record.get("owner_user_id") or "") == owner_user_id


def get_document(
    manager: Any,
    course_id: str,
    document_id: str,
    *,
    owner_user_id: str,
) -> Optional[dict[str, Any]]:
    try:
        records = manager.get_knowledge_base_index(course_id, aggregate=True)
    except TypeError as exc:
        # Lightweight adapters outside CourseStorageManager may predate scope
        # filtering; the production manager always performs the aggregate
        # lookup required for leaf documents.
        if "aggregate" not in str(exc):
            raise
        records = manager.get_knowledge_base_index(course_id)
    for record in records:
        if str(record.get("id") or "") != document_id:
            continue
        return dict(record) if _can_access(record, owner_user_id) else None
    return None


def patch_document(
    manager: Any,
    catalog_id: str,
    document_id: str,
    **fields: Any,
) -> dict[str, Any]:
    with _lock:
        records = manager.get_knowledge_base_index(catalog_id)
        updated: Optional[dict[str, Any]] = None
        next_records: list[dict[str, Any]] = []
        for item in records:
            record = dict(item)
            if str(record.get("id") or "") == document_id:
                record.update(fields)
                record["updated_at"] = _now()
                updated = record
            next_records.append(record)
        if updated is None:
            raise KeyError(document_id)
        if not manager.save_knowledge_base_index(catalog_id, next_records):
            raise OSError("保存知识库文档状态失败")
        return updated


def initialize_document(
    manager: Any,
    course_id: str,
    document_id: str,
) -> dict[str, Any]:
    return patch_document(
        manager,
        course_id,
        document_id,
        status="received",
        active_index_version=None,
        pending_index_version=None,
        page_count=0,
        chunk_count=0,
        failed_units=0,
        parser_name=None,
        embedding_profile_id=None,
        indexed_at=None,
        last_job_id=None,
        error_code=None,
        error_message=None,
    )


def mark_document_ready(
    manager: Any,
    course_id: str,
    document_id: str,
    *,
    rag_index_key: str,
    chunk_count: int,
    page_count: int = 0,
    active_index_version: str | None = None,
    parser_name: str | None = None,
    embedding_profile_id: str | None = None,
) -> dict[str, Any]:
    """Update mutable index metadata without ever changing the public ID."""
    return patch_document(
        manager,
        course_id,
        document_id,
        status="ready",
        rag_index_key=str(rag_index_key or "").strip(),
        active_index_version=active_index_version,
        pending_index_version=None,
        page_count=max(0, int(page_count or 0)),
        chunk_count=max(0, int(chunk_count or 0)),
        failed_units=0,
        parser_name=parser_name,
        embedding_profile_id=embedding_profile_id,
        indexed_at=_now(),
        error_code=None,
        error_message=None,
    )


def submit_index_job(
    *,
    manager: Any,
    rag_system: Any,
    course_id: str,
    document_id: str,
    owner_user_id: str,
    force_reindex: bool,
    existing_job: Optional[EduJob] = None,
    storage_scope: str = "course",
) -> EduJob:
    document = get_document(
        manager, course_id, document_id, owner_user_id=owner_user_id
    )
    if document is None:
        raise KeyError(document_id)
    active_job = (
        get_job(str(document.get("last_job_id") or ""))
        if document.get("last_job_id")
        else None
    )
    if (
        existing_job is None
        and active_job is not None
        and active_job.status in ACTIVE_JOB_STATUSES
    ):
        raise ValueError("该文档已有处理任务正在进行")
    title = str(document.get("filename") or document.get("name") or "知识库文档")
    job = existing_job or create_job(
        kind=JobKind.RAG_IMPORT,
        owner_user_id=owner_user_id,
        course_id=course_id,
        scope_type=str(document.get("scope_type") or "course"),
        scope_id=document.get("scope_id"),
        input_summary={
            "title": title,
            "document_id": document_id,
            "force_reindex": force_reindex,
        },
    )
    pending_version = f"idx_{uuid.uuid4().hex[:12]}"
    patch_document(
        manager,
        course_id,
        document_id,
        last_job_id=job.edu_job_id,
        pending_index_version=pending_version,
        status="indexing" if document.get("active_index_version") else "received",
        error_code=None,
        error_message=None,
    )

    from app.services.platform_task_handlers import enqueue_platform_task
    from app.services.runtime_config_resolver import runtime_config_resolver

    return enqueue_platform_task(
        job=job,
        workflow_type="rag_document_index",
        command={
            "course_id": course_id,
            "document_id": document_id,
            "force_reindex": force_reindex,
            "pending_version": pending_version,
            "storage_scope": str(storage_scope or "course"),
        },
        runtime_config_snapshot=runtime_config_resolver.capture_snapshot(
            owner_user_id
        ),
    )


def _stage_status(stage: str) -> str:
    normalized = str(stage or "").lower()
    if normalized in {"queued", "loading_pdf"}:
        return "parsing"
    if normalized == "splitting":
        return "chunking"
    if normalized == "embedding":
        return "embedding"
    return "indexing"


def run_index_job(
    *,
    manager: Any,
    rag_system: Any,
    course_id: str,
    document_id: str,
    owner_user_id: str,
    force_reindex: bool,
    pending_version: str,
    job_id: str,
) -> None:
    document = get_document(
        manager, course_id, document_id, owner_user_id=owner_user_id
    )
    if document is None:
        return
    relative_path = str(document.get("path") or "")
    full_path = manager.get_course_dir(course_id) / relative_path

    def on_progress(progress: int, stage: str) -> None:
        current = get_job(job_id)
        if current is None or current.status not in ACTIVE_JOB_STATUSES:
            return
        status = _stage_status(stage)
        patch_document(manager, course_id, document_id, status=status)
        update_job(
            job_id,
            status=JobStatus.RUNNING,
            step=status,
            progress=max(1, min(99, int(progress))),
            message={
                "parsing": "正在读取文档内容",
                "chunking": "正在切分可检索片段",
                "embedding": "正在生成向量",
                "indexing": "正在写入检索索引",
            }[status],
        )

    try:
        on_progress(1, "queued")
        library_type = str(document.get("library_type") or "course").strip().lower()
        is_personal = library_type == "personal"
        scope_type = (
            "personal"
            if is_personal
            else str(document.get("scope_type") or "course").strip()
        )
        scope_id = (
            str(document.get("scope_id") or f"personal:{owner_user_id}").strip()
            if is_personal
            else str(document.get("scope_id") or "").strip()
        )
        result = rag_system.import_document(
            str(full_path),
            force_reimport=force_reindex,
            progress_callback=on_progress,
            owner=owner_user_id,
            metadata_overrides={
                "course_id": "" if is_personal else course_id,
                "library_type": library_type,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "knowledge_node_id": "" if is_personal else scope_id,
                "course_document_id": document_id,
            },
        )
        current = get_job(job_id)
        if current is None or current.status not in ACTIVE_JOB_STATUSES:
            patch_document(
                manager,
                course_id,
                document_id,
                status="ready"
                if document.get("active_index_version")
                else "failed",
                pending_index_version=None,
            )
            return
        resolved = resolve_rag_document(
            rag_system, str(full_path), owner=owner_user_id
        )
        rag_record = dict(resolved.record) if resolved is not None else {}
        chunk_count = int(
            rag_record.get("chunk_count") or result.get("chunk_count") or 0
        )
        page_count = int(rag_record.get("page_count") or 0)
        updated = mark_document_ready(
            manager,
            course_id,
            document_id,
            rag_index_key=resolved.index_key if resolved is not None else "",
            chunk_count=chunk_count,
            page_count=page_count,
            active_index_version=pending_version,
            parser_name="rag_v2",
            embedding_profile_id=str(
                getattr(getattr(rag_system, "embedding_client", None), "model", "")
                or "default"
            ),
        )
        update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="文档已可用于问答",
            result_ref={
                "resource_type": "knowledge_document",
                "course_id": course_id,
                "document_id": document_id,
                "index_version": pending_version,
                "chunk_count": updated.get("chunk_count", 0),
            },
        )
    except Exception as exc:  # noqa: BLE001 - persist a safe, actionable state
        latest = get_document(
            manager, course_id, document_id, owner_user_id=owner_user_id
        ) or document
        has_active = bool(latest.get("active_index_version"))
        patch_document(
            manager,
            course_id,
            document_id,
            status="ready" if has_active else "failed",
            pending_index_version=None,
            error_code="RAG_INDEX_FAILED",
            error_message=str(exc),
        )
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="failed",
            message="文档处理失败",
            error_code="RAG_INDEX_FAILED",
            error_message=str(exc),
        )


def test_retrieval(
    *,
    manager: Any,
    rag_system: Any,
    course_id: str,
    document_id: str,
    owner_user_id: str,
    query: str,
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    document = get_document(
        manager, course_id, document_id, owner_user_id=owner_user_id
    )
    if document is None:
        raise KeyError(document_id)
    if document.get("status") not in {"ready", "partially_ready"}:
        raise ValueError("文档尚未完成索引，暂不能测试检索")
    full_path = manager.get_course_dir(course_id) / str(document.get("path") or "")
    resolved = resolve_rag_document(
        rag_system,
        document.get("rag_index_key") or str(full_path),
        owner=owner_user_id,
    )
    if resolved is None:
        raise ValueError("当前索引版本不可用，请重建索引")
    ranked = rag_system.retrieve_documents(
        query,
        top_k=top_k,
        allowed_sources=[resolved.source_key],
    )
    hits = []
    for chunk in ranked[:top_k]:
        metadata = chunk.get("metadata") or {}
        page = metadata.get("page")
        try:
            normalized_page = int(page) + 1 if page is not None else None
        except (TypeError, ValueError):
            normalized_page = None
        score = chunk.get("rerank_score")
        if score is None:
            score = chunk.get("rrf_score", chunk.get("combined_score", 0.0))
        hits.append(
            {
                "chunk_id": str(chunk.get("id") or ""),
                "content": str(chunk.get("content") or "")[:1200],
                "score": round(float(score or 0.0), 6),
                "page": normalized_page,
                "timestamp": metadata.get("timestamp")
                or metadata.get("timecode"),
                "reranked": chunk.get("rerank_score") is not None,
            }
        )
    return {
        "document_id": document_id,
        "index_version": str(document.get("active_index_version") or ""),
        "query": query,
        "hits": hits,
        "elapsed_ms": max(0, round((time.perf_counter() - started) * 1000)),
    }
