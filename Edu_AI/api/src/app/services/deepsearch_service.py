"""Deepsearch service layer — LLM orchestration, crawling, content cleaning, and RAG import.

Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

from app.deepsearch_importer import (
    build_personal_research_document,
)
from app.chat.workflows.report.image_downloader import localize_image
from app.integrations.websearch import ExtractResult, WebSearchHit, extract_tavily, rerank_bocha, search_bocha
from app.services import crawl_batch_store
from app.services.personal_knowledge_service import PersonalKnowledgeService
from app.services.runtime_config_resolver import runtime_config_resolver
from modules.rag_v2.api import get_rag_system


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


# ---------------------------------------------------------------------------
# pipeline steps
# ---------------------------------------------------------------------------


def _execute_search(query: str, max_urls: Optional[int]) -> List[WebSearchHit]:
    runtime_search = runtime_config_resolver.resolve("web_search")
    final_count = max(1, int(max_urls or int(os.getenv("WEB_SEARCH_DEFAULT_COUNT", "10") or "10")))
    recall_count = max(final_count, int(os.getenv("BOCHA_SEARCH_RECALL_COUNT", "50") or "50"))
    recall_count = min(recall_count, 50)
    print(f"[DeepSearch] phase=search provider=bocha query={query!r} max_urls={final_count} recall={recall_count}")
    hits = search_bocha(
        query,
        count=recall_count,
        freshness=os.getenv("WEB_SEARCH_FRESHNESS", "noLimit"),
        api_key=str(runtime_search.get("api_key") or os.getenv("BOCHA_API_KEY", "")),
        base_url=str(
            runtime_search.get("base_url")
            or os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn")
        ),
        timeout=float(runtime_search.get("timeout_seconds") or 15),
    )
    hits = _rerank_hits(query, hits, final_count)
    return hits[:final_count]


def _rerank_hits(query: str, hits: list[WebSearchHit], top_n: int) -> list[WebSearchHit]:
    if len(hits) <= 1:
        return hits
    enabled = str(os.getenv("BOCHA_RERANK_ENABLED", "true") or "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return hits
    documents = [_hit_rerank_text(hit) for hit in hits]
    runtime_search = runtime_config_resolver.resolve("web_search")
    try:
        ranked = rerank_bocha(
            query,
            documents,
            top_n=min(max(1, int(top_n or len(hits))), len(hits)),
            api_key=str(runtime_search.get("api_key") or os.getenv("BOCHA_API_KEY", "")),
            base_url=str(
                runtime_search.get("base_url")
                or os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn")
            ),
            model=str(
                runtime_search.get("model")
                or os.getenv("BOCHA_RERANK_MODEL", "gte-rerank")
            ),
            timeout=float(
                runtime_search.get("timeout_seconds")
                or os.getenv("BOCHA_RERANK_TIMEOUT_S", "15")
                or "15"
            ),
        )
    except Exception as exc:
        print(f"[DeepSearch] phase=rerank provider=bocha status=error error={type(exc).__name__}: {exc}")
        return hits
    if not ranked:
        print("[DeepSearch] phase=rerank provider=bocha status=empty fallback=original_order")
        return hits
    ordered: list[WebSearchHit] = []
    seen: set[int] = set()
    for item in ranked:
        if item.index in seen:
            continue
        ordered.append(hits[item.index])
        seen.add(item.index)
    ordered.extend(hit for idx, hit in enumerate(hits) if idx not in seen)
    print(
        "[DeepSearch] phase=rerank provider=bocha status=success "
        f"input={len(hits)} returned={len(ranked)} top_score={ranked[0].score if ranked else 0:.4f}"
    )
    return ordered


def _hit_rerank_text(hit: WebSearchHit) -> str:
    parts = [
        f"Title: {hit.title}",
        f"Content: {hit.content}",
        f"Site: {hit.site or ''}",
        f"Date: {hit.date or ''}",
        f"URL: {hit.url}",
    ]
    return "\n".join(part for part in parts if part.strip())


def _execute_extract(
    hits: List[WebSearchHit],
    query: str,
    max_urls: Optional[int],
    crawl_timeout: Optional[int],
) -> CrawlBatchResult:
    urls = [hit.url for hit in hits[: max_urls or len(hits)]]
    extract_depth = os.getenv("WEB_EXTRACT_DEPTH_FULL", "advanced")
    timeout = int(crawl_timeout or int(os.getenv("WEB_EXTRACT_TIMEOUT_S", "60") or "60"))
    max_extract_urls = int(os.getenv("WEB_EXTRACT_MAX_URLS", "20") or "20")
    print(
        "[DeepSearch] phase=extract provider=tavily "
        f"depth={extract_depth} urls={len(urls)} timeout_s={timeout} max_urls={max_extract_urls}"
    )
    extracted = extract_tavily(
        urls,
        depth=extract_depth,
        timeout=timeout,
        api_key=os.getenv("TAVILY_API_KEY", ""),
        base_url=os.getenv("TAVILY_BASE_URL", "https://api.tavily.com"),
        max_urls=max_extract_urls,
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
                content=_append_image_markdown(hit.content, hit.images),
                content_type="summary",
                status="success" if hit.content else "failed",
                error_message=None if hit.content else "empty_summary",
                metadata={
                    "source": "bocha",
                    "bocha_summary": hit.content,
                    "site": hit.site,
                    "date": hit.date,
                    "images": hit.images,
                    "image_count": len(hit.images),
                },
            )
            for hit in hits
        ],
    )


def _crawl_result_from_extract(hit: WebSearchHit, item: ExtractResult) -> CrawlResult:
    images = _merge_images(item.images, hit.images)
    content = _append_image_markdown(item.content or hit.content, images)
    return CrawlResult(
        url=hit.url,
        title=hit.title or hit.url,
        content=content,
        content_type="markdown",
        status=item.status,
        error_message=item.error,
        metadata={
            "source": "bocha+tavily",
            "bocha_summary": hit.content,
            "site": hit.site,
            "date": hit.date,
            "images": images,
            "image_count": len(images),
            "favicon": item.favicon,
        },
    )


def _clean_crawl_results(crawl_batch) -> List[dict]:
    cleaned_results: List[dict] = []
    content_limit = int(os.getenv("DEEPSEARCH_RESULT_CONTENT_MAX_CHARS", "50000") or "50000")

    for idx, result in enumerate(crawl_batch.results, 1):
        content = result.content
        if content and content_limit > 0 and len(content) > content_limit:
            content = content[:content_limit]
        cleaned_results.append(
            {
                "url": result.url,
                "title": result.title,
                "content": content,
                "content_type": result.content_type,
                "status": result.status,
                "error_message": result.error_message,
                "metadata": result.metadata,
                "file_path": result.file_path,
            }
        )

    return cleaned_results


def _merge_images(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for value in group or []:
            url = str(value or "").strip()
            if url and url not in merged:
                merged.append(url)
    return merged


def _append_image_markdown(content: str | None, images: list[str]) -> str | None:
    body = str(content or "").strip()
    if not body or not images:
        return body or None
    existing = set(re.findall(r"!\[[^\]]*]\(([^)]+)\)", body))
    lines = []
    for index, url in enumerate(images[: int(os.getenv("DEEPSEARCH_MAX_INLINE_IMAGES", "8") or "8")], start=1):
        if url in existing:
            continue
        lines.append(f"![Image {index}]({url})")
    if not lines:
        return body
    return f"{body}\n\n## Images\n\n" + "\n\n".join(lines)


def _is_external_image_url(url: str) -> bool:
    return bool(re.match(r"^https?://", str(url or "").strip(), flags=re.IGNORECASE))


def _localize_crawl_batch_images(crawl_batch: CrawlBatchResult, *, owner: str, course_id: Optional[str]) -> None:
    for result in crawl_batch.results:
        images = _merge_images(result.metadata.get("images") or [])
        if not images:
            continue

        localized_images: list[str] = []
        image_assets: list[dict[str, str]] = []
        replacements: dict[str, str] = {}
        for url in images:
            if not _is_external_image_url(url):
                localized_images.append(url)
                continue
            try:
                localized = localize_image(
                    {
                        "url": url,
                        "source_page": result.url,
                        "title": result.title,
                        "alt": result.title,
                        "provenance": {"provider": str(result.metadata.get("source") or "deepsearch")},
                    },
                    owner=owner,
                    course_id=course_id,
                )
            except Exception as exc:
                print(f"[DeepSearch] phase=image_localize status=error url={url} error={type(exc).__name__}: {exc}")
                localized_images.append(url)
                continue

            local_url = str(getattr(localized, "local_url", "") or "").strip()
            local_path = str(getattr(localized, "local_path", "") or "").strip()
            if local_url and local_path:
                localized_images.append(local_url)
                replacements[url] = local_url
                image_assets.append(
                    {
                        "file_path": local_path,
                        "source_url": local_url,
                        "original_url": url,
                    }
                )
            else:
                localized_images.append(url)

        result.metadata["images"] = localized_images
        result.metadata["image_count"] = len(localized_images)
        if image_assets:
            result.metadata["image_assets"] = image_assets
        if result.content and replacements:
            updated_content = result.content
            for source_url, local_url in replacements.items():
                updated_content = updated_content.replace(source_url, local_url)
            result.content = updated_content


def _import_to_knowledge_base(
    crawl_batch,
    owner: str,
    course_id: Optional[str],
    scope_type: Optional[str],
    scope_id: Optional[str],
) -> List[dict]:
    rag_system = get_rag_system()
    service = PersonalKnowledgeService()
    imported_docs: List[dict] = []
    for result in list(crawl_batch.results or []):
        prepared = build_personal_research_document(result)
        if prepared is None:
            continue
        document = service.create_document(
            owner_user_id=owner,
            filename=str(prepared["filename"]),
            file_data=bytes(prepared["file_data"]),
            course_context_id=course_id,
        )
        document = service.set_provenance(
            owner_user_id=owner,
            document_id=str(document["id"]),
            source_url=prepared.get("source_url"),
            source_title=prepared.get("source_title"),
            source_domain=prepared.get("source_domain"),
            source_site_name=prepared.get("source_site_name"),
            doc_kind=prepared.get("doc_kind"),
            deepsearch_batch_id=str(getattr(crawl_batch, "batch_id", "") or ""),
        )
        job = service.submit_index(
            owner_user_id=owner,
            document_id=str(document["id"]),
            rag_system=rag_system,
        )
        imported_docs.append(
            {
                "document_id": str(document["id"]),
                "file_name": str(document.get("filename") or prepared["filename"]),
                "url": prepared.get("source_url"),
                "source_title": prepared.get("source_title"),
                "source_domain": prepared.get("source_domain"),
                "source_site_name": prepared.get("source_site_name"),
                "job_id": str(job.get("edu_job_id") or ""),
                "status": str(job.get("status") or "queued"),
                "library_type": "personal",
                "scope_type": "personal",
            }
        )
    return imported_docs


# ---------------------------------------------------------------------------
# public service API
# ---------------------------------------------------------------------------


def search_web_sources(query: str, max_results: int = 6) -> List[WebSearchHit]:
    """Search and rerank web sources without crawling or importing them."""
    return _execute_search(query, max_results)


def run_deepsearch_and_crawl(
    *,
    query: str,
    owner: str,
    depth: str = "basic",
    max_urls: Optional[int] = 10,
    crawl_timeout: Optional[int] = 60,
    save_to_kb: Optional[bool] = True,
    course_id: Optional[str] = None,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict:
    try:
        hits = _execute_search(query, max_urls)
    except Exception as exc:
        print(f"[DeepSearch] phase=search provider=bocha status=error error={type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "message": f"Bocha 搜索失败: {exc}",
            "query": query,
        }

    if not hits:
        print("[DeepSearch] phase=search provider=bocha status=empty hits=0")
        return {
            "ok": False,
            "message": "深度搜索未找到相关链接",
            "query": query,
        }
    print(
        "[DeepSearch] phase=search provider=bocha status=success "
        f"hits={len(hits)} image_urls={sum(len(hit.images) for hit in hits)}"
    )

    fallback_reason = ""
    if depth == "full":
        try:
            crawl_batch = _execute_extract(hits, query, max_urls, crawl_timeout)
            if crawl_batch.success_count == 0:
                fallback_reason = "tavily_all_failed"
                print("[DeepSearch] phase=extract provider=tavily status=all_failed fallback=bocha_basic")
                crawl_batch = _build_basic_batch(query, hits)
        except Exception as exc:
            fallback_reason = str(exc)
            print(
                "[DeepSearch] phase=extract provider=tavily status=error "
                f"error={type(exc).__name__}: {exc} fallback=bocha_basic"
            )
            crawl_batch = _build_basic_batch(query, hits)
    else:
        crawl_batch = _build_basic_batch(query, hits)
    _localize_crawl_batch_images(crawl_batch, owner=owner, course_id=course_id)
    print(
        "[DeepSearch] phase=content status=ready "
        f"mode={depth} results={crawl_batch.total_urls} success={crawl_batch.success_count} "
        f"failed={crawl_batch.failed_count} chars={sum(len(result.content or '') for result in crawl_batch.results)} "
        f"image_urls={sum(int(result.metadata.get('image_count') or 0) for result in crawl_batch.results)}"
    )

    cleaned_results = _clean_crawl_results(crawl_batch)

    batch_id = crawl_batch_store.save_crawl_batch(crawl_batch, owner=owner)
    crawl_batch.batch_id = batch_id
    print(f"[DeepSearch] phase=batch_store status=saved batch_id={batch_id}")

    imported_docs: List[dict] = []
    archive_error = ""
    if save_to_kb:
        try:
            imported_docs = _import_to_knowledge_base(
                crawl_batch,
                owner=owner,
                course_id=course_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        except Exception as exc:
            archive_error = f"{type(exc).__name__}: {exc}"
            print(f"[DeepSearch] phase=personal_archive status=error error={archive_error}")
    if not save_to_kb:
        archive_status = "not_requested"
    elif not imported_docs:
        archive_status = "failed"
    elif len(imported_docs) < crawl_batch.success_count:
        archive_status = "partial"
    else:
        archive_status = "succeeded"
    print(f"[DeepSearch] phase=rag_import status=done saved_to_kb={bool(save_to_kb)} docs={len(imported_docs)}")
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
        "saved_to_kb": archive_status in {"succeeded", "partial"},
        "saved_to_personal_knowledge": archive_status in {"succeeded", "partial"},
        "archive_status": archive_status,
        "archive_error": archive_error or None,
        "imported_documents": imported_docs,
    }


def get_crawl_results(*, batch_id: str, owner: str | None = None) -> dict:
    batch_result = crawl_batch_store.load_crawl_batch(batch_id, owner=owner)
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


def get_crawl_history(*, limit: int = 20, owner: str | None = None) -> dict:
    batches = crawl_batch_store.list_batches(limit=limit, owner=owner)
    return {"ok": True, "batches": batches}
