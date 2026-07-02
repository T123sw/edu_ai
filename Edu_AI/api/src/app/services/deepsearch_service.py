"""Deepsearch service layer — LLM orchestration, crawling, content cleaning, and RAG import.

Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from app.deepsearch_importer import (
    import_crawl_results_to_rag,
    persist_imported_documents_to_course_kb,
)
from app.integrations.websearch import ExtractResult, WebSearchHit, extract_tavily, search_bocha
from app.services import crawl_batch_store
from core import Config
from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document


@dataclass
class CrawlResult:
    url: str
    title: str
    content: str | None
    content_type: str = "html"
    status: str = "success"
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None


@dataclass
class CrawlBatchResult:
    query: str
    results: list[CrawlResult]
    batch_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_urls(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for result in self.results if result.status == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status != "success")

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


def _execute_search(query: str, max_urls: Optional[int]) -> List[WebSearchHit]:
    count = max(1, int(max_urls or int(os.getenv("WEB_SEARCH_DEFAULT_COUNT", "10") or "10")))
    return search_bocha(
        query,
        count=count,
        freshness=os.getenv("WEB_SEARCH_FRESHNESS", "noLimit"),
        api_key=os.getenv("BOCHA_API_KEY", ""),
        base_url=os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn"),
    )


def _execute_extract(
    hits: List[WebSearchHit],
    query: str,
    max_urls: Optional[int],
    crawl_timeout: Optional[int],
) -> CrawlBatchResult:
    urls = [hit.url for hit in hits[: max_urls or len(hits)]]
    extracted = extract_tavily(
        urls,
        depth=os.getenv("WEB_EXTRACT_DEPTH", "basic"),
        timeout=int(crawl_timeout or int(os.getenv("WEB_EXTRACT_TIMEOUT_S", "30") or "30")),
        api_key=os.getenv("TAVILY_API_KEY", ""),
        base_url=os.getenv("TAVILY_BASE_URL", "https://api.tavily.com"),
        max_urls=int(os.getenv("WEB_EXTRACT_MAX_URLS", "20") or "20"),
    )
    by_url = {item.url: item for item in extracted}
    results: list[CrawlResult] = []
    for hit in hits:
        item = by_url.get(hit.url)
        if item is None:
            continue
        results.append(_crawl_result_from_extract(hit, item))
    return CrawlBatchResult(query=query, results=results)


def _build_basic_batch(query: str, hits: List[WebSearchHit]) -> CrawlBatchResult:
    return CrawlBatchResult(
        query=query,
        results=[
            CrawlResult(
                url=hit.url,
                title=hit.title or hit.url,
                content=hit.content,
                content_type="summary",
                status="success" if hit.content else "failed",
                error_message=None if hit.content else "empty_summary",
                metadata={
                    "source": "bocha",
                    "bocha_summary": hit.content,
                    "site": hit.site,
                    "date": hit.date,
                    "images": hit.images,
                },
            )
            for hit in hits
        ],
    )


def _crawl_result_from_extract(hit: WebSearchHit, item: ExtractResult) -> CrawlResult:
    return CrawlResult(
        url=hit.url,
        title=hit.title or hit.url,
        content=item.content or hit.content,
        content_type="markdown",
        status=item.status,
        error_message=item.error,
        metadata={
            "source": "bocha+tavily",
            "bocha_summary": hit.content,
            "site": hit.site,
            "date": hit.date,
            "images": hit.images,
        },
    )


def _clean_crawl_results(crawl_batch) -> List[dict]:
    cleaned_results: List[dict] = []

    for idx, result in enumerate(crawl_batch.results, 1):
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
    depth: str = "basic",
    max_urls: Optional[int] = 10,
    crawl_timeout: Optional[int] = 30,
    save_to_kb: Optional[bool] = True,
    course_id: Optional[str] = None,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict:
    try:
        hits = _execute_search(query, max_urls)
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Bocha 搜索失败: {exc}",
            "query": query,
        }

    if not hits:
        return {
            "ok": False,
            "message": "深度搜索未找到相关链接",
            "query": query,
        }

    fallback_reason = ""
    if depth == "full":
        try:
            crawl_batch = _execute_extract(hits, query, max_urls, crawl_timeout)
            if crawl_batch.success_count == 0:
                fallback_reason = "tavily_all_failed"
                crawl_batch = _build_basic_batch(query, hits)
        except Exception as exc:
            fallback_reason = str(exc)
            crawl_batch = _build_basic_batch(query, hits)
    else:
        crawl_batch = _build_basic_batch(query, hits)

    cleaned_results = _clean_crawl_results(crawl_batch)

    batch_id = crawl_batch_store.save_crawl_batch(crawl_batch)
    crawl_batch.batch_id = batch_id

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
    sources = [
        {"title": result.title, "url": result.url, "site": result.metadata.get("site")}
        for result in crawl_batch.results
        if result.status == "success"
    ]
    summary = "\n\n".join(
        [str(result.content or "").strip() for result in crawl_batch.results if result.status == "success" and result.content][:3]
    )

    return {
        "ok": True,
        "query": query,
        "batch_id": batch_id,
        "total_urls": crawl_batch.total_urls,
        "success_count": crawl_batch.success_count,
        "failed_count": crawl_batch.failed_count,
        "links": [hit.url for hit in hits],
        "created_at": crawl_batch.created_at.isoformat() if hasattr(crawl_batch.created_at, "isoformat") else None,
        "results": cleaned_results,
        "summary": summary,
        "sources": sources,
        "fallback_reason": fallback_reason,
        "saved_to_kb": bool(save_to_kb),
        "imported_documents": imported_docs,
    }


def get_crawl_results(*, batch_id: str) -> dict:
    batch_result = crawl_batch_store.load_crawl_batch(batch_id)
    if not batch_result:
        return {"ok": False, "message": "批次不存在"}

    return {
        "ok": True,
        "batch_id": batch_id,
        "query": batch_result.get("query"),
        "total_urls": batch_result.get("total_urls"),
        "success_count": batch_result.get("success_count"),
        "failed_count": batch_result.get("failed_count"),
        "created_at": batch_result.get("created_at"),
        "results": batch_result.get("results") or [],
    }


def get_crawl_history(*, limit: int = 20) -> dict:
    batches = crawl_batch_store.list_batches(limit=limit)
    return {"ok": True, "batches": batches}
