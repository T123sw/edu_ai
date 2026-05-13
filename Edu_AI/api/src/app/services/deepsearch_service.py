"""Deepsearch service layer — LLM orchestration, crawling, content cleaning, and RAG import.

Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from app.deepsearch_importer import (
    import_crawl_results_to_rag,
    persist_imported_documents_to_course_kb,
)
from app.deepsearch_loader import load_eduagent_capabilities
from core import Config
from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document

# ---------------------------------------------------------------------------
# EduAgent path setup
# ---------------------------------------------------------------------------

_base_dir = Path(__file__).resolve().parent
_candidate_paths = [
    _base_dir.parent.parent.parent.parent.parent / "EduAgent",
    _base_dir.parent.parent.parent.parent / "EduAgent",
]
_EDU_AGENT_PATH = next((p for p in _candidate_paths if p.exists()), _candidate_paths[0])
if str(_EDU_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(_EDU_AGENT_PATH))

# ---------------------------------------------------------------------------
# EduAgent capability loading
# ---------------------------------------------------------------------------

_capabilities = load_eduagent_capabilities(__file__)
_EDU_AGENT_PATH = _capabilities.edu_agent_path


def _missing_capability(message: str):
    def _raise(*args, **kwargs):
        raise NotImplementedError(message)

    return _raise


if _capabilities.deepsearch_error:
    _deepsearch_large_llm = _missing_capability(
        f"EduAgent deepsearch 未配置: {_capabilities.deepsearch_error}"
    )
else:
    _deepsearch_large_llm = _capabilities.deepsearch_large_llm

if _capabilities.service_error:
    _get_crawler_service = _missing_capability(
        f"EduAgent crawler_service 未配置: {_capabilities.service_error}"
    )
    _ContentCleaner = _missing_capability(
        f"EduAgent content_cleaner 未配置: {_capabilities.service_error}"
    )
    _get_storage_service = _missing_capability(
        f"EduAgent storage_service 未配置: {_capabilities.service_error}"
    )
else:
    _get_crawler_service = _capabilities.get_crawler_service
    _ContentCleaner = _capabilities.ContentCleaner
    _get_storage_service = _capabilities.get_storage_service

# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------


def _safe_slug(text: str, max_len: int = 60) -> str:
    s = (text or "").strip()
    if not s:
        return "untitled"
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s[:max_len].strip()
    return s or "untitled"


def _url_hash(url: str) -> str:
    return hashlib.md5((url or "").encode("utf-8", errors="ignore")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# pipeline steps
# ---------------------------------------------------------------------------


def _execute_deepsearch(query: str, max_urls: Optional[int]) -> List[str]:
    search_result = _deepsearch_large_llm(query)
    if not search_result or not search_result.get("links"):
        return []
    urls = search_result["links"]
    if max_urls:
        urls = urls[:max_urls]
    return urls


def _execute_crawl(
    urls: List[str],
    query: str,
    max_urls: Optional[int],
    crawl_timeout: Optional[int],
):
    crawler_service = _get_crawler_service()
    return crawler_service.crawl_urls(
        urls=urls,
        query=query,
        max_urls=max_urls,
        timeout_per_url=crawl_timeout,
    )


def _clean_crawl_results(crawl_batch) -> List[dict]:
    content_cleaner = _ContentCleaner()
    cleaned_results: List[dict] = []

    for idx, result in enumerate(crawl_batch.results, 1):
        if result.status == "success" and result.file_path:
            if result.content_type == "pdf":
                cleaned = content_cleaner.clean_pdf_content(result.file_path)
            else:
                cleaned = content_cleaner.clean_text_content(
                    result.content or "",
                    result.file_path,
                )
            if "cleaned_content" in cleaned:
                cleaned_content = cleaned.get("cleaned_content", "")
                result.content = cleaned_content
                result.metadata.update(cleaned.get("metadata", {}))

        cleaned_results.append(
            {
                "url": result.url,
                "title": result.title,
                "content": result.content[:2000] if result.content else None,
                "content_type": result.content_type,
                "status": result.status,
                "error_message": result.error_message,
                "metadata": result.metadata,
                "file_path": result.file_path,
            }
        )

    return cleaned_results


def _import_to_knowledge_base(
    crawl_batch,
    owner: str,
    course_id: Optional[str],
    scope_type: Optional[str],
    scope_id: Optional[str],
) -> List[dict]:
    imported_docs: List[dict] = []
    rag_system = get_rag_system()

    imported_docs = import_crawl_results_to_rag(
        results=crawl_batch.results,
        owner=owner,
        rag_system=rag_system,
        documents_root=Config.DOCUMENTS_ROOT,
    )

    dest_dir = Config.DOCUMENTS_ROOT / "web" / owner
    dest_dir.mkdir(parents=True, exist_ok=True)

    for r in crawl_batch.results:
        if r.status != "success":
            continue
        url = r.url or ""
        if not url:
            continue

        title = (r.title or "").strip() or url
        domain = ""
        try:
            domain = (urlparse(url).netloc or "").replace(":", "_")
        except Exception:
            domain = ""

        h = _url_hash(url)

        if r.content_type == "pdf" and r.file_path and Path(r.file_path).exists():
            filename = f"web_{domain or 'pdf'}_{_safe_slug(title, 30)}_{h}.pdf"
            dst = dest_dir / filename
            if not dst.exists():
                dst.write_bytes(Path(r.file_path).read_bytes())
            import_path = str(dst.absolute())
        else:
            filename = f"web_{domain or 'page'}_{_safe_slug(title, 30)}_{h}.md"
            dst = dest_dir / filename

            full_content = ""
            if r.content:
                full_content = r.content
            elif r.file_path and Path(r.file_path).exists():
                try:
                    full_content = Path(r.file_path).read_text(encoding="utf-8")
                except Exception:
                    full_content = r.content or ""

            if not full_content:
                continue

            if not dst.exists():
                md = (
                    f"# {title}\n\n"
                    f"- 来源: {url}\n"
                    f"- 抓取方式: deepsearch+crawl\n\n"
                    f"## 正文\n\n{full_content}\n"
                )
                dst.write_text(md, encoding="utf-8")
            import_path = str(dst.absolute())

        if not Path(import_path).exists():
            continue

        import_result = rag_system.import_document(import_path, force_reimport=False, owner=owner)

        resolved_document = None
        try:
            resolved_document = resolve_rag_document(rag_system, import_path, owner=owner)
            rec = resolved_document.record if resolved_document is not None else None
            if isinstance(rec, dict):
                pretty_name = f"{title}"
                if domain and domain not in pretty_name:
                    pretty_name = f"{pretty_name} - {domain}"
                rec["file_name"] = _safe_slug(pretty_name, 120)
                rec["source_url"] = url
                rec["source_title"] = title
                rec["source_domain"] = domain
                rec["doc_kind"] = "web"
                rec["source_key"] = rec.get("source_key") or resolved_document.source_key
        except Exception:
            pass

        imported_docs.append(
            {
                "file_path": import_path,
                "index_key": resolved_document.index_key if resolved_document is not None else None,
                "file_name": Path(import_path).name,
                "url": url,
            }
        )

    try:
        rag_system._save_index()
    except Exception:
        pass

    if course_id:
        try:
            from core.course_storage import storage_manager

            persist_imported_documents_to_course_kb(
                imported_docs=imported_docs,
                owner=owner,
                course_id=course_id,
                scope_type=scope_type,
                scope_id=scope_id,
                storage_manager=storage_manager,
                rag_system=rag_system,
            )
        except Exception:
            pass

    return imported_docs


# ---------------------------------------------------------------------------
# public service API
# ---------------------------------------------------------------------------


def run_deepsearch_and_crawl(
    *,
    query: str,
    owner: str,
    max_urls: Optional[int] = 10,
    crawl_timeout: Optional[int] = 30,
    save_to_kb: Optional[bool] = True,
    course_id: Optional[str] = None,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict:
    urls = _execute_deepsearch(query, max_urls)
    if not urls:
        return {
            "ok": False,
            "message": "深度搜索未找到相关链接",
            "query": query,
        }

    try:
        crawl_batch = _execute_crawl(urls, query, max_urls, crawl_timeout)
    except Exception as exc:
        return {
            "ok": False,
            "message": f"爬虫启动失败: {exc}",
            "query": query,
            "links": urls,
        }

    cleaned_results = _clean_crawl_results(crawl_batch)

    storage_service = _get_storage_service()
    batch_id = storage_service.save_crawl_batch(crawl_batch)

    imported_docs: List[dict] = []
    if save_to_kb:
        try:
            imported_docs = _import_to_knowledge_base(
                crawl_batch,
                owner=owner,
                course_id=course_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        except Exception:
            pass

    return {
        "ok": True,
        "query": query,
        "batch_id": batch_id,
        "total_urls": crawl_batch.total_urls,
        "success_count": crawl_batch.success_count,
        "failed_count": crawl_batch.failed_count,
        "links": urls,
        "created_at": crawl_batch.created_at.isoformat() if hasattr(crawl_batch.created_at, "isoformat") else None,
        "results": cleaned_results,
        "saved_to_kb": bool(save_to_kb),
        "imported_documents": imported_docs,
    }


def get_crawl_results(*, batch_id: str) -> dict:
    storage_service = _get_storage_service()
    batch_result = storage_service.load_crawl_batch(batch_id)
    if not batch_result:
        return {"ok": False, "message": "批次不存在"}

    return {
        "ok": True,
        "batch_id": batch_id,
        "query": batch_result.query,
        "total_urls": batch_result.total_urls,
        "success_count": batch_result.success_count,
        "failed_count": batch_result.failed_count,
        "created_at": batch_result.created_at.isoformat(),
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "content": r.content[:2000] if r.content else None,
                "content_type": r.content_type,
                "status": r.status,
                "error_message": r.error_message,
                "metadata": r.metadata,
                "file_path": r.file_path,
            }
            for r in batch_result.results
        ],
    }


def get_crawl_history(*, limit: int = 20) -> dict:
    storage_service = _get_storage_service()
    batches = storage_service.list_batches(limit=limit)
    return {"ok": True, "batches": batches}
