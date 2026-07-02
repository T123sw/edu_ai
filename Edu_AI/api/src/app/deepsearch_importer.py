from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from core.course_storage import LIBRARY_TYPE_PERSONAL
from modules.rag_v2.document_resolver import resolve_rag_document


_FULL_WIDTH_BAR = "｜"
_SITE_NAME_KEYS = (
    "source_site_name",
    "site_name",
    "og_site_name",
    "og:site_name",
    "publisher",
)


def _safe_slug(text: str, max_len: int = 60) -> str:
    value = (text or "").strip()
    if not value:
        return "untitled"
    value = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = value[:max_len].strip()
    return value or "untitled"


def _url_hash(url: str) -> str:
    return hashlib.md5((url or "").encode("utf-8", errors="ignore")).hexdigest()[:12]


def _derive_site_name(metadata: Dict[str, Any], domain: str, title: str) -> str:
    for key in _SITE_NAME_KEYS:
        candidate = _safe_slug(str(metadata.get(key) or ""), 80)
        if candidate != "untitled":
            return candidate

    for separator in (" - ", " | ", "_"):
        if separator in title:
            parts = [part.strip() for part in title.split(separator) if part.strip()]
            if len(parts) >= 2:
                return _safe_slug(parts[-1], 80)

    return _safe_slug(domain or "web", 80)


def _compose_deepsearch_file_name(site_name: str, summary_title: str, fallback_title: str) -> str:
    safe_site = _safe_slug(site_name, 80)
    safe_title = _safe_slug(summary_title or fallback_title, 80)
    if safe_site and safe_site != "untitled" and safe_title and safe_site.casefold() != safe_title.casefold():
        return _safe_slug(f"{safe_site}{_FULL_WIDTH_BAR}{safe_title}", 120)
    return _safe_slug(safe_title or safe_site, 120)


def _normalize_paths(values: Any) -> List[str]:
    if isinstance(values, str):
        values = [values]
    normalized: List[str] = []
    for value in values or []:
        candidate = str(value or "").strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _normalize_image_assets(metadata: Dict[str, Any]) -> List[Dict[str, str]]:
    assets = []
    for asset in metadata.get("image_assets") or []:
        if not isinstance(asset, dict):
            continue
        file_path = str(asset.get("file_path") or "").strip()
        source_url = str(asset.get("source_url") or "").strip()
        if not file_path:
            continue
        assets.append(
            {
                "file_path": file_path,
                "source_url": source_url,
            }
        )

    if assets:
        return assets

    return [
        {"file_path": path, "source_url": ""}
        for path in _normalize_paths(metadata.get("image_paths"))
    ]


def _build_web_markdown(title: str, url: str, full_content: str) -> str:
    return (
        f"# {title}\n\n"
        f"- Source: {url}\n"
        f"- Crawl Mode: deepsearch+crawl\n\n"
        f"## Content\n\n{full_content.strip()}\n"
    )


def import_crawl_results_to_rag(
    *,
    results: Iterable[Any],
    owner: str,
    rag_system: Any,
    documents_root: Path,
    image_importer: Optional[Callable[..., Dict[str, Any]]] = None,
    min_content_length: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if image_importer is None:
        from modules.rag_v2.rag_main.api import import_local_image_file as image_importer

    destination_dir = Path(documents_root) / "web" / owner
    destination_dir.mkdir(parents=True, exist_ok=True)

    imported_docs: List[Dict[str, Any]] = []
    minimum_length = (
        min_content_length
        if min_content_length is not None
        else int(os.getenv("DEEPSEARCH_MIN_CONTENT_LENGTH", "200"))
    )
    max_images_per_page = int(os.getenv("DEEPSEARCH_MAX_IMAGES_PER_PAGE", "12"))

    for result in results:
        if getattr(result, "status", "") != "success":
            continue

        url = str(getattr(result, "url", "") or "").strip()
        if not url:
            continue

        title = str(getattr(result, "title", "") or "").strip() or url
        try:
            domain = (urlparse(url).netloc or "").replace(":", "_")
        except Exception:
            domain = ""
        url_digest = _url_hash(url)

        content_type = str(getattr(result, "content_type", "text") or "text").lower()
        source_file_path = str(getattr(result, "file_path", "") or "").strip()
        metadata = getattr(result, "metadata", {}) or {}
        image_assets = _normalize_image_assets(metadata)
        linked_images: List[Dict[str, Any]] = []
        source_icon_url: Optional[str] = None
        source_icon_path: Optional[str] = None

        if content_type == "pdf" and source_file_path and Path(source_file_path).exists():
            filename = f"web_{domain or 'pdf'}_{_safe_slug(title, 30)}_{url_digest}.pdf"
            destination_path = destination_dir / filename
            if not destination_path.exists():
                destination_path.write_bytes(Path(source_file_path).read_bytes())

            import_path = str(destination_path.absolute())
            rag_system.import_document(import_path, force_reimport=False, owner=owner)
            resolved_document = resolve_rag_document(rag_system, import_path, owner=owner)
            record = resolved_document.record if resolved_document is not None else None
        else:
            filename = f"web_{domain or 'page'}_{_safe_slug(title, 30)}_{url_digest}.md"
            destination_path = destination_dir / filename

            full_content = str(getattr(result, "content", "") or "")
            if not full_content and source_file_path and Path(source_file_path).exists():
                try:
                    full_content = Path(source_file_path).read_text(encoding="utf-8")
                except Exception:
                    full_content = ""

            if len(full_content.strip()) < minimum_length:
                continue

            markdown = _build_web_markdown(title, url, full_content)
            destination_path.write_text(markdown, encoding="utf-8")

            import_path = str(destination_path.absolute())
            rag_system.import_document(import_path, force_reimport=False, owner=owner)
            resolved_document = resolve_rag_document(rag_system, import_path, owner=owner)

            updated_content = full_content
            needs_reimport = False

            raw_image_assets = image_assets[:max_images_per_page]
            raw_site_icon_path = _normalize_paths(metadata.get("site_icon_path"))
            site_icon_path = raw_site_icon_path[0] if raw_site_icon_path else None

            if resolved_document is not None and isinstance(resolved_document.record, dict):
                for image_asset in raw_image_assets:
                    image_path = image_asset["file_path"]
                    if site_icon_path and Path(image_path).resolve() == Path(site_icon_path).resolve():
                        continue
                    try:
                        image_result = image_importer(
                            image_path,
                            owner=owner,
                            include_in_search=False,
                            hidden_in_list=True,
                            doc_kind="web_image",
                            extra_metadata={
                                "source_url": url,
                                "source_title": title,
                                "source_domain": domain,
                                "parent_index_key": resolved_document.index_key,
                            },
                        )
                    except Exception:
                        continue

                    source_image_url = image_asset.get("source_url")
                    local_image_url = image_result.get("image_url")
                    if source_image_url and local_image_url:
                        replaced_content = updated_content.replace(source_image_url, local_image_url)
                        if replaced_content != updated_content:
                            updated_content = replaced_content
                            needs_reimport = True

                    linked_images.append(
                        {
                            "image_path": image_result.get("image_path") or image_path,
                            "image_url": local_image_url,
                            "image_name": Path(image_path).name,
                            "source": "crawl",
                        }
                    )

                if site_icon_path:
                    try:
                        icon_result = image_importer(
                            site_icon_path,
                            owner=owner,
                            include_in_search=False,
                            hidden_in_list=True,
                            doc_kind="site_icon",
                            extra_metadata={
                                "source_url": url,
                                "source_title": title,
                                "source_domain": domain,
                                "parent_index_key": resolved_document.index_key,
                            },
                        )
                        source_icon_path = icon_result.get("image_path") or site_icon_path
                        source_icon_url = icon_result.get("image_url")
                    except Exception:
                        source_icon_path = site_icon_path

                if needs_reimport:
                    markdown = _build_web_markdown(title, url, updated_content)
                    destination_path.write_text(markdown, encoding="utf-8")
                    rag_system.import_document(import_path, force_reimport=True, owner=owner)
                    resolved_document = resolve_rag_document(rag_system, import_path, owner=owner)

                record = resolved_document.record if resolved_document is not None else None
            else:
                record = None

        if isinstance(record, dict):
            site_name = _derive_site_name(metadata, domain, title)
            # 摘要直接复用博查搜索返回的 summary，不再触发 LLM 二次生成（旧链路已删除）。
            summary = str(metadata.get("bocha_summary") or "").strip()

            pretty_name = title
            if domain and domain not in pretty_name:
                pretty_name = f"{pretty_name} - {domain}"

            if summary:
                record["summary"] = summary
                record["summary_updated_at"] = datetime.now().isoformat()

            record["file_name"] = _compose_deepsearch_file_name(site_name, "", pretty_name)
            record["source_url"] = url
            record["source_title"] = title
            record["source_domain"] = domain
            record["source_site_name"] = site_name
            record["doc_kind"] = "web"
            record["source_key"] = record.get("source_key") or (
                resolved_document.source_key if resolved_document is not None else None
            )
            record["linked_images"] = linked_images
            if source_icon_path:
                record["source_icon_path"] = source_icon_path
            if source_icon_url:
                record["source_icon_url"] = source_icon_url

        imported_docs.append(
            {
                "file_path": import_path,
                "index_key": resolved_document.index_key if resolved_document is not None else None,
                "file_name": record.get("file_name") if isinstance(record, dict) else Path(import_path).name,
                "url": url,
            }
        )

    try:
        rag_system._save_index()
    except Exception:
        pass

    return imported_docs


def persist_imported_documents_to_course_kb(
    *,
    imported_docs: Iterable[Dict[str, Any]],
    owner: str,
    course_id: str,
    scope_type: Optional[str],
    scope_id: Optional[str],
    storage_manager: Any,
    rag_system: Any,
) -> List[Dict[str, Any]]:
    persisted_docs: List[Dict[str, Any]] = []

    for imported_doc in imported_docs:
        import_path = str(imported_doc.get("file_path") or "").strip()
        if not import_path:
            continue

        source_path = Path(import_path)
        if not source_path.exists():
            continue

        file_name = str(imported_doc.get("file_name") or source_path.name).strip() or source_path.name
        index_key = str(imported_doc.get("index_key") or "").strip() or None
        source_url = str(imported_doc.get("url") or imported_doc.get("source_url") or "").strip() or None

        try:
            file_data = source_path.read_bytes()
        except Exception:
            continue

        relative_path = storage_manager.save_knowledge_base_file(
            course_id,
            file_data,
            file_name,
            scope_type=scope_type,
            scope_id=scope_id,
            library_type=LIBRARY_TYPE_PERSONAL,
            owner_user_id=owner,
            promoted_from_document_id=index_key,
        )
        if not relative_path:
            continue
        normalized_relative_path = str(relative_path).replace("\\", "/")

        index = storage_manager.get_knowledge_base_index(course_id)
        latest = None
        for item in reversed(index):
            if str(item.get("path") or "").replace("\\", "/") == normalized_relative_path:
                latest = item
                break

        if isinstance(latest, dict):
            if source_url:
                latest["url"] = source_url
                latest["source_url"] = source_url
            latest["doc_kind"] = "web"
            storage_manager.save_knowledge_base_index(course_id, index)

        if index_key:
            record = getattr(rag_system, "document_index", {}).get(index_key)
            if isinstance(record, dict):
                record["hidden_in_list"] = True

        persisted_docs.append(
            {
                "relative_path": normalized_relative_path,
                "file_name": file_name,
                "index_key": index_key,
                "url": source_url,
            }
        )

    try:
        rag_system._save_index()
    except Exception:
        pass

    return persisted_docs
