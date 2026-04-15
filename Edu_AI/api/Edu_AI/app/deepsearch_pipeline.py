from __future__ import annotations

import sys
import os
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core import Config
from rag_v2.api import get_rag_system
from rag_v2.document_resolver import resolve_rag_document


# 添加EduAgent到Python路径
# 从 D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\deepsearch_pipeline.py 到 D:\Edu_AI_1\EduAgent
# 可能路径：D:\Edu_AI_1\EduAgent 或 D:\Edu_AI_1\Edu_AI\EduAgent
base_dir = Path(__file__).resolve().parent
candidate_paths = [
    base_dir.parent.parent.parent.parent.parent / "EduAgent",
    base_dir.parent.parent.parent.parent / "EduAgent",
]
EDU_AGENT_PATH = next((p for p in candidate_paths if p.exists()), candidate_paths[0])
if str(EDU_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(EDU_AGENT_PATH))


try:
    from services.crawler_service import get_crawler_service
    from services.content_cleaner import ContentCleaner
    from services.storage_service import get_storage_service
    from deepsearch import deepsearch_large_llm
except ImportError as e:
    def deepsearch_large_llm(query: str):
        raise NotImplementedError("EduAgent模块未找到")

    def get_crawler_service():
        raise NotImplementedError("EduAgent模块未找到")

    def ContentCleaner():
        raise NotImplementedError("EduAgent模块未找到")

    def get_storage_service():
        raise NotImplementedError("EduAgent模块未找到")


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



def run_deepsearch_pipeline(
    *,
    query: str,
    owner: Optional[str] = None,
    max_urls: int = 10,
    crawl_timeout: int = 30,
    save_to_kb: bool = True,
) -> Dict[str, Any]:
    owner_name = owner or "unknown"

    search_result = deepsearch_large_llm(query)
    if not search_result or not search_result.get("links"):
        return {"ok": False, "message": "深度搜索未找到相关链接", "query": query}

    urls = search_result.get("links") or []
    if max_urls:
        urls = urls[:max_urls]

    crawler_service = get_crawler_service()
    crawl_batch = crawler_service.crawl_urls(
        urls=urls,
        query=query,
        max_urls=max_urls,
        timeout_per_url=crawl_timeout,
    )

    content_cleaner = ContentCleaner()
    for result in crawl_batch.results:
        if result.status != "success" or not result.file_path:
            continue
        if result.content_type == "pdf":
            cleaned = content_cleaner.clean_pdf_content(result.file_path)
        else:
            cleaned = content_cleaner.clean_text_content(result.content or "", result.file_path)
        if "cleaned_content" in cleaned:
            result.content = cleaned.get("cleaned_content", "")
            result.metadata.update(cleaned.get("metadata", {}))

    storage_service = get_storage_service()
    batch_id = storage_service.save_crawl_batch(crawl_batch)

    imported_docs: List[Dict[str, str]] = []
    if save_to_kb:
        rag_system = get_rag_system()
        dest_dir = (Config.DOCUMENTS_ROOT / "web" / owner_name)
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
                full_content = r.content or ""
                if not full_content and r.file_path and Path(r.file_path).exists():
                    try:
                        full_content = Path(r.file_path).read_text(encoding="utf-8")
                    except Exception:
                        full_content = ""
                if not full_content:
                    continue
                min_content_length = int(os.getenv("DEEPSEARCH_MIN_CONTENT_LENGTH", "200"))
                if len(full_content.strip()) < min_content_length:
                    print(
                        f"[API] [入库] 跳过内容过短的页面: {url} "
                        f"(长度={len(full_content.strip())}, 阈值={min_content_length})"
                    )
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

            import_result = rag_system.import_document(import_path, force_reimport=False, owner=owner_name)
            resolved_document = None
            try:
                resolved_document = resolve_rag_document(rag_system, import_path, owner=owner_name)
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

            imported_docs.append({
                "file_path": import_path,
                "index_key": resolved_document.index_key if resolved_document is not None else None,
                "file_name": Path(import_path).name,
                "url": url,
            })

        try:
            rag_system._save_index()
        except Exception:
            pass

    return {
        "ok": True,
        "query": query,
        "links": urls,
        "batch_id": batch_id,
        "imported": imported_docs,
    }
