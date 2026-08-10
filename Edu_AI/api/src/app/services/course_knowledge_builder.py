"""Build a traceable Chinese course knowledge base from reviewed open textbooks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import requests

from app.services.job_store import EduJob, JobKind, JobStatus, create_job, update_job
from core.course_storage import LIBRARY_TYPE_COURSE, CourseStorageManager


BUILDER_VERSION = "course-kb-zh-v1"
SUPPLEMENT_BUILDER_VERSION = "course-kb-supplement-v1"
_AI_INGESTION_DENY_MARKERS = (
    "may not be used in the training of large language models",
    "may not be ingested into large language models",
    "may not be ingested into generative ai",
    "不得用于训练大型语言模型",
    "不得用于生成式人工智能",
)
_ALLOWED_LICENSE_MARKERS = (
    "cc-by-4.0",
    "cc by 4.0",
    "creativecommons.org/licenses/by/4.0",
    "cc-by-sa-4.0",
    "cc by-sa 4.0",
    "creativecommons.org/licenses/by-sa/4.0",
    "cc-by-nc-sa-4.0",
    "cc by-nc-sa 4.0",
    "creativecommons.org/licenses/by-nc-sa/4.0",
    "cc0-1.0",
    "creativecommons.org/publicdomain/zero/1.0",
)
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def _store_knowledge_audit(record_key: str, payload: Mapping[str, Any]) -> str | None:
    if os.getenv("APP_STATE_PERSISTENCE_MODE", "json").strip().lower() != "postgres":
        return None
    from app.persistence.dependencies import get_postgres_app_state_repository

    get_postgres_app_state_repository().put(
        "knowledge_audit",
        record_key,
        payload,
    )
    return f"postgres://app_state/knowledge_audit/{record_key}"
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_TOC_CAPTION_RE = re.compile(r'^\s*-\s+caption:\s*["\']?(.+?)["\']?\s*$')
_TOC_FILE_RE = re.compile(r"^\s*-\s+file:\s*([\w.-]+)\s*$")
_MKDOCS_NAV_GROUP_RE = re.compile(r"^\s{2}-\s+(.+?):\s*$")
_MKDOCS_NAV_PAGE_RE = re.compile(r"^\s{4}-\s+(?:(.+?):\s+)?([^\s#]+\.md)\s*$")
_NON_CURRICULAR_PART_MARKERS = (
    "前言",
    "附录",
    "参考文献",
    "纸质书",
    "preface",
    "appendix",
    "bibliography",
    "references",
)
_NON_CURRICULAR_SOURCE_PATH_MARKERS = (
    "/chapter_hello_algo/",
    "/chapter_preface/",
    "/chapter_appendix/",
    "/chapter_reference/",
    "/chapter_paperbook/",
)


@dataclass(frozen=True)
class OpenTextbookSource:
    source_id: str
    course_ids: tuple[str, ...]
    title: str
    landing_url: str
    publisher: str
    license_name: str
    license_url: str
    allowed_hosts: tuple[str, ...]
    repository: str = ""
    repository_path: str = ""
    toc_file: str = ""
    content_root: str = ""
    toc_format: str = "jupyter"
    source_language: str = "en"
    output_language: str = "zh-CN"
    attribution: str = ""
    usage_restriction: str = ""


OPEN_TEXTBOOK_SOURCES: dict[str, OpenTextbookSource] = {
    "hello-algo-zh": OpenTextbookSource(
        source_id="hello-algo-zh",
        course_ids=("computational-thinking", "data-structures"),
        title="《Hello 算法》中文课程知识图谱",
        landing_url="https://www.hello-algo.com/",
        publisher="krahets 与《Hello 算法》开源贡献者",
        license_name="CC BY-NC-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
        allowed_hosts=("api.github.com", "raw.githubusercontent.com", "www.hello-algo.com"),
        repository="krahets/hello-algo",
        repository_path="",
        content_root="docs",
        toc_file="mkdocs.yml",
        toc_format="mkdocs",
        source_language="zh-CN",
        output_language="zh-CN",
        attribution="原作《Hello 算法》，作者 krahets 及开源贡献者。",
        usage_restriction="仅限实验室内部、个人学习与其他非商业用途；改编内容须保持相同许可。",
    ),
    "think-and-compute-zh": OpenTextbookSource(
        source_id="think-and-compute-zh",
        course_ids=("computational-thinking",),
        title="《Think and Compute：数字人文计算导论》中文适配版",
        landing_url="https://thinkcompute.github.io/",
        publisher="博洛尼亚大学 Digital Humanities and Digital Knowledge 课程团队",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        allowed_hosts=("api.github.com", "raw.githubusercontent.com", "thinkcompute.github.io"),
        repository="thinkcompute/thinkcompute.github.io",
        repository_path="think_and_compute",
        toc_file="_toc.yml",
        source_language="en",
        output_language="zh-CN",
        attribution=(
            "改编自 Silvio Peroni、Ivan Heibi、Arcangelo Massari（2025）"
            "《Think and Compute: a Primer for Digital Humanists》，原作采用 CC BY 4.0。"
        ),
    ),
}

SUPPLEMENTARY_SOURCE_POLICIES: dict[str, dict[str, str]] = {
    "oi-wiki.org": {
        "site_name": "OI Wiki",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "language": "zh-CN",
    },
    "docs.python.org": {
        "site_name": "Python 官方中文文档",
        "license": "PSF License Version 2",
        "license_url": "https://docs.python.org/zh-cn/3/license.html",
        "language": "zh-CN",
    },
    "zh.wikipedia.org": {
        "site_name": "维基百科（中文）",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "language": "zh-CN",
    },
    "en.wikipedia.org": {
        "site_name": "Wikipedia",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "language": "en",
    },
    "www.csunplugged.org": {
        "site_name": "CS Unplugged 中文开放课程",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "language": "zh-CN",
    },
    "classic.csunplugged.org": {
        "site_name": "CS Unplugged",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "language": "en",
    },
}

CURATED_SUPPLEMENT_URLS: tuple[tuple[str, str], ...] = (
    ("二叉搜索树", "https://oi-wiki.org/ds/bst/"),
    ("AVL 树", "https://oi-wiki.org/ds/avl/"),
    ("数组与链表", "https://oi-wiki.org/ds/linked-list/"),
    ("数组 vs. 链表", "https://oi-wiki.org/ds/linked-list/"),
    ("栈与队列", "https://oi-wiki.org/ds/stack/"),
    ("栈的典型应用", "https://oi-wiki.org/ds/stack/"),
    ("哈希表", "https://oi-wiki.org/ds/hash/"),
    ("动态规划", "https://oi-wiki.org/dp/basic/"),
    ("分治", "https://oi-wiki.org/basic/divide-and-conquer/"),
    ("回溯", "https://oi-wiki.org/search/backtracking/"),
    ("贪心", "https://oi-wiki.org/basic/greedy/"),
    ("桶排序", "https://oi-wiki.org/basic/bucket-sort/"),
    ("二分查找", "https://oi-wiki.org/basic/binary/"),
    ("排序", "https://oi-wiki.org/basic/sort-intro/"),
    ("复杂度", "https://oi-wiki.org/basic/complexity/"),
    ("初识算法", "https://oi-wiki.org/basic/complexity/"),
    ("搜索", "https://oi-wiki.org/search/dfs/"),
    ("堆", "https://oi-wiki.org/ds/binary-heap/"),
    ("数据结构", "https://oi-wiki.org/ds/"),
    ("图", "https://oi-wiki.org/graph/concept/"),
    ("树", "https://oi-wiki.org/ds/bst/"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().casefold()


def _is_non_curricular_part(title: Any) -> bool:
    normalized = re.sub(r"\s+", " ", str(title or "")).strip().casefold()
    return normalized == "序" or any(marker in normalized for marker in _NON_CURRICULAR_PART_MARKERS)


def _course_topic_group_title(title: Any) -> str:
    value = re.sub(r"\s+", " ", str(title or "")).strip()
    return re.sub(r"^第\s*\d+\s*章\s*", "", value).strip() or value


def _is_non_curricular_generated_record(record: Mapping[str, Any]) -> bool:
    if record.get("generated_by") != BUILDER_VERSION:
        return False
    source_url = str(record.get("source_url") or record.get("url") or "").casefold()
    return any(marker in source_url for marker in _NON_CURRICULAR_SOURCE_PATH_MARKERS)


def remove_non_curricular_generated_records(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
) -> dict[str, Any]:
    """Delete book-only front/back matter from the active course library and RAG index."""
    course_dir = manager.get_course_dir(course_id).resolve()
    entries = [dict(item) for item in manager.get_knowledge_base_index(course_id)]
    removed = [item for item in entries if _is_non_curricular_generated_record(item)]
    kept = [item for item in entries if not _is_non_curricular_generated_record(item)]
    warnings: list[str] = []
    for record in removed:
        relative_path = str(record.get("path") or "").replace("\\", "/").strip()
        candidate = (course_dir / relative_path).resolve()
        try:
            candidate.relative_to(course_dir / "knowledge_base" / "documents")
        except ValueError:
            warnings.append(f"跳过知识库目录外的路径：{relative_path}")
            continue
        try:
            rag_system.delete_document(str(candidate), owner=owner_user_id)
        except Exception as exc:
            warnings.append(f"删除检索索引失败：{candidate.name}: {exc}")
        if candidate.is_file():
            candidate.unlink()
    if removed and not manager.save_knowledge_base_index(course_id, kept):
        raise OSError("保存课程型知识库清理结果失败")
    return {
        "removed_count": len(removed),
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def clean_stale_knowledge_records(
    *,
    manager: CourseStorageManager,
    course_id: str,
    apply: bool,
) -> dict[str, Any]:
    """Remove index-only placeholders and duplicate paths without deleting real files."""
    course_dir = manager.get_course_dir(course_id).resolve()
    entries = [dict(item) for item in manager.get_knowledge_base_index(course_id)]
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for record in entries:
        relative_path = str(record.get("path") or "").replace("\\", "/").strip()
        normalized_path = _canonical_path(relative_path)
        reason = ""
        if not relative_path:
            reason = "missing_path"
        else:
            candidate = (course_dir / relative_path).resolve()
            try:
                candidate.relative_to(course_dir)
            except ValueError:
                reason = "unsafe_path"
            else:
                if not candidate.is_file():
                    reason = "missing_file"
                elif normalized_path in seen_paths:
                    reason = "duplicate_path"

        if reason:
            removed.append({"id": record.get("id"), "path": relative_path, "reason": reason})
            continue
        seen_paths.add(normalized_path)
        kept.append(record)

    backup_path: Path | str | None = None
    if apply and removed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        record_key = f"{course_id}:clean:{stamp}"
        backup_path = _store_knowledge_audit(record_key, {
            "course_id": course_id,
            "operation": "clean",
            "created_at": utc_now(),
            "records": entries,
        })
        if backup_path is None:
            backup_dir = course_dir / "knowledge_base" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"index-before-clean-{stamp}.json"
            backup_path.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if not manager.save_knowledge_base_index(course_id, kept):
            raise OSError("保存清理后的课程知识库索引失败")

    removed_by_reason: dict[str, int] = {}
    for item in removed:
        reason = str(item["reason"])
        removed_by_reason[reason] = removed_by_reason.get(reason, 0) + 1
    return {
        "course_id": course_id,
        "applied": apply,
        "before_count": len(entries),
        "after_count": len(kept),
        "removed_count": len(removed),
        "removed_by_reason": dict(sorted(removed_by_reason.items())),
        "removed": removed,
        "backup_path": str(backup_path) if backup_path else None,
    }


def quarantine_knowledge_records(
    *,
    manager: CourseStorageManager,
    course_id: str,
    record_ids: Sequence[str],
    reason: str,
    apply: bool,
) -> dict[str, Any]:
    """Move explicitly selected records out of the active library without destroying them."""
    selected_ids = {str(item).strip() for item in record_ids if str(item).strip()}
    course_dir = manager.get_course_dir(course_id).resolve()
    entries = [dict(item) for item in manager.get_knowledge_base_index(course_id)]
    selected = [item for item in entries if str(item.get("id") or "") in selected_ids]
    kept = [item for item in entries if str(item.get("id") or "") not in selected_ids]
    if not selected:
        return {
            "course_id": course_id,
            "applied": apply,
            "quarantined_count": 0,
            "quarantine_path": None,
        }

    resolved_files: list[tuple[dict[str, Any], Path]] = []
    for record in selected:
        relative_path = str(record.get("path") or "").replace("\\", "/").strip()
        candidate = (course_dir / relative_path).resolve()
        try:
            candidate.relative_to(course_dir / "knowledge_base" / "documents")
        except ValueError as exc:
            raise ValueError(f"拒绝隔离知识库目录以外的文件：{relative_path}") from exc
        if candidate.is_file():
            resolved_files.append((record, candidate))

    quarantine_dir: Path | None = None
    if apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = course_dir / "knowledge_base" / "backups"
        quarantine_dir = backup_dir / f"quarantine-{stamp}"
        quarantine_dir.mkdir(parents=True, exist_ok=False)
        audit_payload = {
            "course_id": course_id,
            "operation": "quarantine",
            "reason": str(reason or "manual cleanup"),
            "created_at": utc_now(),
            "records_before": entries,
            "records": selected,
            "quarantine_path": str(quarantine_dir),
        }
        audit_uri = _store_knowledge_audit(
            f"{course_id}:quarantine:{stamp}", audit_payload
        )
        if audit_uri is None:
            (backup_dir / f"index-before-quarantine-{stamp}.json").write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (quarantine_dir / "manifest.json").write_text(
                json.dumps(audit_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        moved: list[tuple[Path, Path]] = []
        try:
            for index, (_, source_path) in enumerate(resolved_files, start=1):
                target = quarantine_dir / f"{index:03d}-{source_path.name}"
                shutil.move(str(source_path), str(target))
                moved.append((source_path, target))
            if not manager.save_knowledge_base_index(course_id, kept):
                raise OSError("保存隔离后的课程知识库索引失败")
        except Exception:
            for source_path, target in reversed(moved):
                if target.exists() and not source_path.exists():
                    shutil.move(str(target), str(source_path))
            raise

    return {
        "course_id": course_id,
        "applied": apply,
        "quarantined_count": len(selected),
        "file_count": len(resolved_files),
        "quarantine_path": str(quarantine_dir) if quarantine_dir else None,
    }


def reset_course_knowledge_graph(
    *,
    manager: CourseStorageManager,
    course_id: str,
    apply: bool,
) -> dict[str, Any]:
    """Back up a legacy graph and replace it with an explicit unbuilt state."""
    course_dir = manager.get_course_dir(course_id).resolve()
    graph_path = course_dir / "knowledge_graph.json"
    previous = manager.get_knowledge_graph(course_id)
    backup_path: Path | None = None
    if apply and previous:
        backup_dir = course_dir / "knowledge_base" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = backup_dir / f"knowledge-graph-before-reset-{stamp}.json"
        shutil.copy2(graph_path, backup_path)
        clean_graph = {
            "id": "root",
            "label": "课程知识图谱（待构建）",
            "children": [],
            "data": {
                "level": 0,
                "summary": "旧占位图谱已清理，请从已审核的开放教材重新构建。",
                "hasChildren": False,
                "type": "course",
                "content_language": "zh-CN",
                "status": "empty",
            },
        }
        if not manager.save_knowledge_graph(course_id, clean_graph):
            raise OSError("保存清理后的课程知识图谱失败")
    return {
        "course_id": course_id,
        "applied": apply,
        "had_graph": bool(previous),
        "backup_path": str(backup_path) if backup_path else None,
    }


def validate_open_textbook_license(source: OpenTextbookSource, evidence: str) -> None:
    normalized = str(evidence or "").casefold()
    for marker in _AI_INGESTION_DENY_MARKERS:
        if marker.casefold() in normalized:
            raise ValueError("来源条款明确禁止 generative AI / 大模型摄取，已拒绝采集")
    license_text = f"{source.license_name} {source.license_url} {normalized}".casefold()
    if not any(marker in license_text for marker in _ALLOWED_LICENSE_MARKERS):
        raise ValueError("来源未提供可验证的 CC BY、CC BY-SA 或 CC0 许可")
    is_noncommercial = (
        "-nc" in license_text or "noncommercial" in license_text or "非商业" in license_text
    )
    if is_noncommercial and not source.usage_restriction:
        raise ValueError("仅限非商业使用的正文必须配置明确的内部使用限制")


def resolve_open_textbook_source(course_id: str, source_id: str = "auto") -> OpenTextbookSource:
    normalized = str(source_id or "auto").strip()
    if normalized != "auto":
        source = OPEN_TEXTBOOK_SOURCES.get(normalized)
        if source is None or course_id not in source.course_ids:
            raise ValueError("该课程没有已审核的中文开放教材来源")
        return source
    for source in OPEN_TEXTBOOK_SOURCES.values():
        if course_id in source.course_ids:
            return source
    raise ValueError("该课程尚未配置已审核的中文开放教材来源")


def _parse_toc(toc_text: str) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for line in str(toc_text or "").splitlines():
        caption_match = _TOC_CAPTION_RE.match(line)
        if caption_match:
            active = {"title": caption_match.group(1).strip(), "files": []}
            parts.append(active)
            continue
        file_match = _TOC_FILE_RE.match(line)
        if file_match:
            if active is None:
                active = {"title": "课程正文", "files": []}
                parts.append(active)
            active["files"].append(file_match.group(1).strip())
    return [part for part in parts if part["files"]]


def _parse_mkdocs_nav(toc_text: str) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    in_nav = False
    for line in str(toc_text or "").splitlines():
        if line.strip() == "nav:":
            in_nav = True
            continue
        if not in_nav:
            continue
        group_match = _MKDOCS_NAV_GROUP_RE.match(line)
        if group_match:
            clean_title = re.sub(r"<[^>]+>|&nbsp;", " ", group_match.group(1))
            active = {"title": re.sub(r"\s+", " ", clean_title).strip(), "files": []}
            parts.append(active)
            continue
        page_match = _MKDOCS_NAV_PAGE_RE.match(line)
        if page_match and active is not None:
            path = page_match.group(2).strip()
            active["files"].append(path[:-3] if path.endswith(".md") else path)
    return [part for part in parts if part["files"]]


def _markdown_from_notebook(raw_text: str) -> str:
    payload = json.loads(raw_text)
    blocks: list[str] = []
    for cell in payload.get("cells") or []:
        source = "".join(cell.get("source") or []).strip()
        if not source:
            continue
        if cell.get("cell_type") == "code":
            blocks.append(f"```python\n{source}\n```")
        elif cell.get("cell_type") == "markdown":
            blocks.append(source)
    return "\n\n".join(blocks)


def _github_raw_url(
    source: OpenTextbookSource,
    revision: str,
    file_stem: str,
    suffix: str,
    *,
    root: str | None = None,
) -> str:
    repository_root = source.repository_path if root is None else root
    path = "/".join(
        item.strip("/")
        for item in (repository_root, f"{file_stem}{suffix}")
        if item.strip("/")
    )
    return f"https://raw.githubusercontent.com/{source.repository}/{revision}/{path}"


def _http_get_with_retry(
    client: httpx.Client,
    url: str,
    *,
    attempts: int = 4,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = client.get(url)
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            last_error = httpx.HTTPStatusError(
                f"可重试响应: {response.status_code}",
                request=response.request,
                response=response,
            )
        except httpx.TransportError as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(min(8.0, 0.5 * (2**attempt)))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"请求失败: {url}")


def fetch_open_textbook_pages_from_site(
    source: OpenTextbookSource,
    *,
    max_pages: int = 160,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Fallback crawler for an open textbook's published HTML site.

    This path is used when the repository host is unavailable. It keeps HTML
    tables, code and images by converting the article DOM to Markdown, while
    image URLs stay absolute for the asset materializer.
    """
    from bs4 import BeautifulSoup
    from markdownify import markdownify as html_to_markdown

    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    owns_client = client is None
    active = client or httpx.Client(timeout=30, follow_redirects=True, headers=headers)
    try:
        landing_response = _http_get_with_retry(active, source.landing_url)
        landing_response.raise_for_status()
        validate_open_textbook_license(source, landing_response.text)
        landing_soup = BeautifulSoup(landing_response.text, "html.parser")
        landing_host = urlparse(source.landing_url).netloc.casefold()
        page_urls: list[str] = []
        seen: set[str] = set()
        for anchor in landing_soup.select("a[href]"):
            url = urljoin(source.landing_url, str(anchor.get("href") or ""))
            parsed = urlparse(url)
            if parsed.netloc.casefold() != landing_host:
                continue
            clean_url = parsed._replace(fragment="", query="").geturl()
            path = parsed.path.casefold()
            if not path.endswith((".html", "/")):
                continue
            if any(marker in path for marker in ("genindex", "search", "404", "license")):
                continue
            if clean_url in seen or clean_url.rstrip("/") == source.landing_url.rstrip("/"):
                continue
            seen.add(clean_url)
            page_urls.append(clean_url)
            if len(page_urls) >= max(1, min(int(max_pages), 200)):
                break

        pages: list[dict[str, Any]] = []
        revision_parts: list[str] = []
        for page_url in page_urls:
            response = _http_get_with_retry(active, page_url)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            main = soup.select_one("article[role='main'], main, article, .bd-article, .document")
            if main is None:
                continue
            for element in main.select("script, style, nav, footer, form, .headerlink"):
                element.decompose()
            for image in main.select("img[src]"):
                image["src"] = urljoin(page_url, str(image.get("src") or ""))
            markdown = html_to_markdown(str(main), heading_style="ATX").strip()
            if len(markdown) < 300:
                continue
            file_stem = Path(urlparse(page_url).path).stem or f"page-{len(pages) + 1}"
            pages.append(
                {
                    "part_title": "",
                    "file_stem": file_stem,
                    "url": page_url,
                    "raw_url": page_url,
                    "content": markdown,
                }
            )
            revision_parts.append(hashlib.sha256(response.content).hexdigest())
        revision = hashlib.sha256("\n".join(revision_parts).encode("utf-8")).hexdigest()
        if not pages:
            raise ValueError("开放教材站点未抓取到可用正文")
        return pages, revision
    finally:
        if owns_client:
            active.close()


def fetch_open_textbook_pages(
    source: OpenTextbookSource,
    *,
    max_pages: int = 160,
    client: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], str]:
    if not source.repository or not source.toc_file:
        raise ValueError("开放教材来源缺少仓库或目录配置")
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    owns_client = client is None
    active = client or httpx.Client(timeout=30, follow_redirects=True, headers=headers)
    try:
        try:
            repository_response = _http_get_with_retry(
                active, f"https://api.github.com/repos/{source.repository}"
            )
        except httpx.TransportError:
            if source.landing_url:
                return fetch_open_textbook_pages_from_site(
                    source,
                    max_pages=max_pages,
                    client=active,
                )
            raise
        repository_response.raise_for_status()
        repository = repository_response.json()
        default_branch = str(repository.get("default_branch") or "main")
        commit_response = _http_get_with_retry(
            active,
            f"https://api.github.com/repos/{source.repository}/commits/{default_branch}"
        )
        commit_response.raise_for_status()
        revision = str(commit_response.json().get("sha") or "").strip()
        if not revision:
            raise ValueError("无法确定开放教材的不可变版本")
        license_info = repository.get("license") or {}
        license_evidence = " ".join(
            [str(license_info.get("spdx_id") or ""), str(license_info.get("name") or "")]
        )
        validate_open_textbook_license(source, license_evidence)

        toc_url = _github_raw_url(
            source,
            revision,
            Path(source.toc_file).stem,
            Path(source.toc_file).suffix,
        )
        toc_response = _http_get_with_retry(active, toc_url)
        toc_response.raise_for_status()
        toc_text = toc_response.text
        validate_open_textbook_license(source, f"{license_evidence}\n{toc_text}")
        parts = _parse_mkdocs_nav(toc_text) if source.toc_format == "mkdocs" else _parse_toc(toc_text)

        pages: list[dict[str, Any]] = []
        for part in parts:
            for file_stem in part["files"]:
                if len(pages) >= max(1, min(int(max_pages), 200)):
                    return pages, revision
                raw_text = ""
                raw_url = ""
                for suffix in (".md", ".ipynb"):
                    candidate = _github_raw_url(
                        source,
                        revision,
                        file_stem,
                        suffix,
                        root=source.content_root or source.repository_path,
                    )
                    response = _http_get_with_retry(active, candidate)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    raw_text = response.text
                    raw_url = candidate
                    if suffix == ".ipynb":
                        raw_text = _markdown_from_notebook(raw_text)
                    break
                if not raw_text.strip():
                    continue
                pages.append(
                    {
                        "part_title": part["title"],
                        "file_stem": file_stem,
                        "url": (
                            f"{source.landing_url.rstrip('/')}/{file_stem.removesuffix('/index')}/"
                            if source.toc_format == "mkdocs"
                            else f"{source.landing_url.rstrip('/')}/{file_stem}.html"
                        ),
                        "raw_url": raw_url,
                        "content": raw_text,
                    }
                )
        return pages, revision
    finally:
        if owns_client:
            active.close()


def _split_translation_chunks(markdown: str, max_chars: int = 9000) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    in_code_block = False
    for line in str(markdown or "").splitlines(keepends=True):
        is_fence = line.lstrip().startswith("```")
        if current and not in_code_block and current_size + len(line) > max_chars:
            chunks.append("".join(current).strip())
            current = []
            current_size = 0
        current.append(line)
        current_size += len(line)
        if is_fence:
            in_code_block = not in_code_block
    if current:
        chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def translate_markdown_to_chinese(markdown: str, *, explicit_env_path: str | None = None) -> str:
    text = str(markdown or "").strip()
    if not text:
        return ""
    if len(_CHINESE_RE.findall(text)) >= max(20, len(text) // 8):
        return text
    _ = explicit_env_path
    from app.services.runtime_config_resolver import runtime_config_resolver

    config = runtime_config_resolver.resolve("llm")
    api_base = str(config.get("base_url") or "").strip().rstrip("/")
    if api_base and not api_base.endswith(("/v1", "/api/v1")):
        api_base = f"{api_base}/v1"
    api_key = str(config.get("api_key") or "").strip()
    model = str(config.get("model") or "").strip()
    if not api_base or not api_key or not model:
        raise RuntimeError("中文教材翻译所需的 LLM 配置不完整")
    translated_chunks: list[str] = []
    for chunk in _split_translation_chunks(text):
        payload = {
            "model": model,
            "temperature": 0,
            "max_tokens": 16384,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的计算机教材翻译。把输入完整翻译为简体中文；保留 Markdown 层级、"
                        "代码块、公式、URL、引用标号和专有名词英文缩写；不得删节、扩写或添加解释。"
                    ),
                },
                {"role": "user", "content": chunk},
            ],
        }
        response = None
        for attempt in range(5):
            try:
                response = requests.post(
                    f"{api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=180,
                )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
            except requests.RequestException:
                if attempt == 4:
                    raise
            if attempt < 4:
                time.sleep(min(8.0, 0.5 * (2**attempt)))
        if response is None:
            raise RuntimeError("教材中文翻译请求未返回响应")
        response.raise_for_status()
        body = response.json()
        content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        if not str(content).strip():
            raise RuntimeError("教材中文翻译返回空内容")
        translated_chunk = str(content).strip()
        if len(translated_chunk) < max(80, len(chunk) // 4):
            raise RuntimeError("教材中文翻译疑似被截断，请稍后重试")
        translated_chunks.append(translated_chunk)
    return "\n\n".join(translated_chunks)


def _strip_heading_markup(value: str) -> str:
    text = re.sub(r"\{[^{}]*\}\s*$", "", str(value or "")).strip()
    return re.sub(r"[*_`]+", "", text).strip()


def _parse_translated_page(page: Mapping[str, Any]) -> dict[str, Any]:
    lines = str(page.get("content") or "").splitlines()
    title = str(page.get("file_stem") or "课程章节")
    intro: list[str] = []
    sections: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    in_code = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_code = not in_code
        heading = None if in_code else _HEADING_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            heading_title = _strip_heading_markup(heading.group(2))
            if level == 1 and heading_title:
                title = heading_title
                continue
            if level == 2 and heading_title:
                active = {"title": heading_title, "content_lines": [line]}
                sections.append(active)
                continue
        if active is None:
            intro.append(line)
        else:
            active["content_lines"].append(line)
    return {
        **dict(page),
        "title": title,
        "intro": "\n".join(intro).strip(),
        "sections": [
            {"title": item["title"], "content": "\n".join(item["content_lines"]).strip()}
            for item in sections
        ],
    }


def build_graph_from_textbook_pages(
    *,
    source: OpenTextbookSource,
    pages: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chapters: list[dict[str, Any]] = []
    chapter_parts: list[str] = []
    materials: list[dict[str, Any]] = []
    for chapter_index, raw_page in enumerate(pages, start=1):
        if _is_non_curricular_part(raw_page.get("part_title")):
            continue
        page = _parse_translated_page(raw_page) if "title" not in raw_page else dict(raw_page)
        page_url = str(page.get("url") or source.landing_url)
        sections = list(page.get("sections") or [])
        section_nodes: list[dict[str, Any]] = []
        if sections:
            for section_index, section in enumerate(sections, start=1):
                node_id = f"chapter-{chapter_index}-section-{section_index}"
                section_nodes.append(
                    {
                        "id": node_id,
                        "label": str(section.get("title") or f"第 {section_index} 节"),
                        "children": [],
                        "data": {
                            "level": 2,
                            "summary": "教材原文对应小节",
                            "hasChildren": False,
                            "type": "section",
                            "source_url": page_url,
                            "source_license": source.license_name,
                            "content_language": source.output_language,
                        },
                    }
                )
                materials.append(
                    {
                        "title": f"{page.get('title')}｜{section.get('title')}",
                        "content": str(section.get("content") or ""),
                        "scope_id": node_id,
                        "source_url": page_url,
                        "raw_url": page.get("raw_url"),
                    }
                )
        else:
            node_id = f"chapter-{chapter_index}"
            materials.append(
                {
                    "title": str(page.get("title") or f"第 {chapter_index} 章"),
                    "content": str(page.get("content") or page.get("intro") or ""),
                    "scope_id": node_id,
                    "source_url": page_url,
                    "raw_url": page.get("raw_url"),
                }
            )
        chapters.append(
            {
                "id": f"chapter-{chapter_index}",
                "label": str(page.get("title") or f"第 {chapter_index} 章"),
                "children": section_nodes,
                "data": {
                    "level": 1,
                    "summary": str(page.get("intro") or "")[:240],
                    "hasChildren": bool(section_nodes),
                    "type": "chapter",
                    "source_url": page_url,
                    "source_license": source.license_name,
                    "content_language": source.output_language,
                },
            }
        )
        chapter_parts.append(str(page.get("part_title") or "").strip())

    graph_children = chapters
    if source.toc_format == "mkdocs" and any(chapter_parts):
        grouped: list[dict[str, Any]] = []
        by_title: dict[str, dict[str, Any]] = {}
        for chapter, part_title in zip(chapters, chapter_parts):
            group_title = _course_topic_group_title(part_title) if part_title else "其他内容"
            group = by_title.get(group_title)
            if group is None:
                group = {
                    "id": f"part-{len(grouped) + 1}",
                    "label": group_title,
                    "children": [],
                    "data": {
                        "level": 1,
                        "summary": "教材原始章级目录",
                        "hasChildren": True,
                        "type": "chapter_group",
                        "source_url": source.landing_url,
                        "source_license": source.license_name,
                        "content_language": source.output_language,
                    },
                }
                grouped.append(group)
                by_title[group_title] = group
            chapter["data"]["level"] = 2
            chapter["data"]["type"] = "page"
            for section in chapter.get("children") or []:
                section["data"]["level"] = 3
            group["children"].append(chapter)
        graph_children = grouped
    graph = {
        "id": "root",
        "label": source.title,
        "children": graph_children,
        "data": {
            "level": 0,
            "summary": f"依据开放教材构建；资料语言为简体中文。{source.attribution}",
            "hasChildren": bool(graph_children),
            "type": "course",
            "source_url": source.landing_url,
            "source_license": source.license_name,
            "source_publisher": source.publisher,
            "content_language": source.output_language,
            "builder_version": BUILDER_VERSION,
        },
    }
    return graph, materials


def _safe_material_filename(source_id: str, title: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{source_url}\n{title}".encode("utf-8")).hexdigest()[:16]
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", title).strip(" .-")[:70]
    return f"kbbuild-{source_id}-{safe_title or 'material'}-{digest}.md"


def _materialize_remote_assets(
    markdown: str,
    *,
    raw_url: str,
    asset_dir: Path,
    markdown_asset_prefix: str,
    allowed_hosts: Sequence[str],
) -> tuple[str, list[dict[str, Any]]]:
    """Download Markdown images beside the document and rewrite links locally."""
    content = str(markdown or "")
    pattern = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)")
    matches = list(pattern.finditer(content))
    if not matches:
        return content, []
    if not raw_url:
        raise ValueError("教材包含图片，但缺少可用于解析资源地址的 raw_url")

    replacements: dict[str, str] = {}
    assets: list[dict[str, Any]] = []
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        for match in matches:
            original = match.group("target").strip().strip('"').strip("'")
            target_without_title = original.split(" ", 1)[0]
            if target_without_title.startswith("data:"):
                raise ValueError("教材图片使用 data URL，必须先落盘后才能入库")
            resolved_url = urljoin(raw_url, target_without_title)
            host = urlparse(resolved_url).netloc.casefold().split(":", 1)[0]
            if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
                raise ValueError(f"教材图片来源不在白名单中: {host}")
            if resolved_url in replacements:
                continue
            response = _http_get_with_retry(client, resolved_url)
            response.raise_for_status()
            content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].lower()
            if not content_type.startswith("image/"):
                raise ValueError(f"教材资源不是图片: {resolved_url}")
            if len(response.content) > 15 * 1024 * 1024:
                raise ValueError(f"教材图片超过 15MB 限制: {resolved_url}")
            suffix = Path(urlparse(resolved_url).path).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
                suffix = ".png" if content_type == "image/png" else ".jpg"
            digest = hashlib.sha256(resolved_url.encode("utf-8")).hexdigest()[:16]
            filename = f"{digest}{suffix}"
            asset_dir.mkdir(parents=True, exist_ok=True)
            asset_path = asset_dir / filename
            asset_path.write_bytes(response.content)
            local_target = f"{markdown_asset_prefix}/{filename}"
            replacements[resolved_url] = local_target
            assets.append(
                {
                    "source_url": resolved_url,
                    "relative_path": local_target,
                    "content_type": content_type,
                    "size": len(response.content),
                }
            )

    def replace(match: re.Match[str]) -> str:
        original = match.group("target").strip().strip('"').strip("'")
        target_without_title = original.split(" ", 1)[0]
        resolved_url = urljoin(raw_url, target_without_title)
        return f"![{match.group('alt')}]({replacements[resolved_url]})"

    return pattern.sub(replace, content), assets


def _persist_material(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    source: OpenTextbookSource,
    revision: str,
    material: Mapping[str, Any],
) -> dict[str, Any]:
    title = str(material.get("title") or "教材资料")
    source_url = str(material.get("source_url") or source.landing_url)
    filename = _safe_material_filename(source.source_id, title, source_url)
    expected_relative_path = f"knowledge_base/documents/{filename}"
    for existing in manager.get_knowledge_base_index(course_id):
        if (
            _canonical_path(existing.get("path")) == _canonical_path(expected_relative_path)
            and existing.get("generated_by") == BUILDER_VERSION
            and existing.get("source_revision") == revision
            and existing.get("status") == "ready"
        ):
            existing_path = manager.get_course_dir(course_id) / expected_relative_path
            if existing_path.is_file():
                return {
                    "document_id": existing["id"],
                    "scope_id": existing.get("scope_id"),
                    "source_url": source_url,
                    "reused": True,
                }
    is_native_chinese = source.source_language.casefold().startswith("zh")
    language_notice = "原生简体中文" if is_native_chinese else "简体中文（由开放许可原文翻译/适配）"
    translation_notice = "原生中文资料，未经过机器翻译" if is_native_chinese else "机器翻译/中文适配，保留原文链接供核验"
    material_content, linked_assets = _materialize_remote_assets(
        str(material.get("content") or ""),
        raw_url=str(material.get("raw_url") or ""),
        asset_dir=(
            manager.get_course_dir(course_id)
            / "knowledge_base"
            / "documents"
            / f"{Path(filename).stem}.assets"
        ),
        markdown_asset_prefix=f"{Path(filename).stem}.assets",
        allowed_hosts=source.allowed_hosts,
    )
    body = (
        f"# {title}\n\n"
        f"> 来源：[{source.publisher}]({source_url})  \n"
        f"> 许可：[{source.license_name}]({source.license_url})  \n"
        f"> 语言：{language_notice}  \n"
        f"> 版本：{revision}  \n"
        f"> 署名：{source.attribution}  \n"
        f"> 使用限制：{source.usage_restriction or '遵循来源许可'}\n\n"
        f"{material_content.strip()}\n"
    )
    relative_path = manager.save_knowledge_base_file(
        course_id,
        body.encode("utf-8"),
        filename,
        scope_type="knowledge_point",
        scope_id=str(material.get("scope_id") or ""),
        library_type=LIBRARY_TYPE_COURSE,
    )
    if not relative_path:
        raise OSError(f"保存教材节点资料失败：{title}")
    full_path = manager.get_course_dir(course_id) / relative_path
    import_result = rag_system.import_document(
        str(full_path),
        force_reimport=False,
        owner=owner_user_id,
        metadata_overrides={
            "course_id": course_id,
            "library_type": LIBRARY_TYPE_COURSE,
            "scope_type": str(material.get("scope_type") or "knowledge_point"),
            "scope_id": str(material.get("scope_id") or ""),
            "knowledge_node_id": str(material.get("scope_id") or ""),
        },
    )
    index = manager.get_knowledge_base_index(course_id)
    record = next(
        item for item in reversed(index)
        if _canonical_path(item.get("path")) == _canonical_path(relative_path)
    )
    record.update(
        {
            "url": source_url,
            "source_url": source_url,
            "source_title": title,
            "source_domain": urlparse(source_url).netloc,
            "source_site_name": source.publisher,
            "source_license": source.license_name,
            "source_license_url": source.license_url,
            "source_revision": revision,
            "source_language": source.source_language,
            "content_language": source.output_language,
            "translation_notice": translation_notice,
            "usage_restriction": source.usage_restriction or None,
            "authority_tier": "reviewed_open_textbook",
            "generated_by": BUILDER_VERSION,
            "retrieved_at": utc_now(),
            "doc_kind": "web",
            "status": "ready",
            "chunk_count": int(import_result.get("chunk_count") or 0),
            "indexed_at": utc_now(),
            "linked_assets": linked_assets,
        }
    )
    manager.save_knowledge_base_index(course_id, index)
    return {"document_id": record["id"], "scope_id": record["scope_id"], "source_url": source_url}


def build_course_knowledge_base(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    source_id: str = "auto",
    max_pages: int = 160,
    clean_placeholders: bool = True,
    translator: Callable[[str], str] | None = None,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, Any]:
    source = resolve_open_textbook_source(course_id, source_id)
    report = clean_stale_knowledge_records(
        manager=manager,
        course_id=course_id,
        apply=clean_placeholders,
    )
    curricular_cleanup = remove_non_curricular_generated_records(
        manager=manager,
        rag_system=rag_system,
        course_id=course_id,
        owner_user_id=owner_user_id,
    )
    if progress:
        progress(8, "source_audit", "已完成开放许可与现有数据检查")
    raw_pages, revision = fetch_open_textbook_pages(source, max_pages=max_pages)
    if not raw_pages:
        raise RuntimeError("开放教材没有可用章节")
    if progress:
        progress(18, "fetching", f"已获取 {len(raw_pages)} 个教材章节")

    translate = translator or translate_markdown_to_chinese
    translated_pages: list[dict[str, Any] | None] = [None] * len(raw_pages)
    total = len(raw_pages)
    cache_dir = (
        manager.get_course_dir(course_id)
        / "knowledge_base"
        / "build_cache"
        / source.source_id
        / revision
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    def translate_page(index: int, page: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        file_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(page.get("file_stem") or index))
        cache_path = cache_dir / f"{file_stem}.zh-CN.md"
        translated = ""
        if cache_path.is_file():
            translated = cache_path.read_text(encoding="utf-8").strip()
        if not _CHINESE_RE.search(translated):
            original_content = str(page.get("content") or "")
            translated = (
                original_content
                if source.source_language.casefold().startswith("zh")
                else translate(original_content)
            )
            cache_path.write_text(translated, encoding="utf-8")
        if not _CHINESE_RE.search(translated):
            raise RuntimeError(f"章节未成功转换为中文：{page.get('file_stem')}")
        return index, _parse_translated_page({**page, "content": translated})

    curricular_pages: list[tuple[int, Mapping[str, Any]]] = []
    for index, page in enumerate(raw_pages):
        if _is_non_curricular_part(page.get("part_title")):
            # Keep the original position so stable scope IDs do not shift, but do
            # not translate or cache book-only front/back matter.
            translated_pages[index] = dict(page)
        else:
            curricular_pages.append((index, page))

    completed = total - len(curricular_pages)
    with ThreadPoolExecutor(max_workers=min(3, total), thread_name_prefix="course-kb-zh") as pool:
        futures = {
            pool.submit(translate_page, index, page): index
            for index, page in curricular_pages
        }
        for future in as_completed(futures):
            page_index, translated_page = future.result()
            translated_pages[page_index] = translated_page
            completed += 1
            if progress:
                progress(
                    18 + round(completed / total * 42),
                    "translating",
                    f"正在生成中文教材资料 {completed}/{total}",
                )

    graph, materials = build_graph_from_textbook_pages(
        source=source,
        pages=[page for page in translated_pages if page is not None],
    )
    course_info = manager.get_course_info(course_id) or {}
    course_title = str(course_info.get("title") or "课程").strip()
    graph["label"] = f"{course_title}课程知识图谱"
    graph["data"]["summary"] = "面向课程教学组织的中文知识图谱；教材仅作为经过审核的基础来源之一。"
    persisted: list[dict[str, Any]] = []
    warnings: list[str] = []
    material_total = max(1, len(materials))
    for index, material in enumerate(materials, start=1):
        try:
            persisted.append(
                _persist_material(
                    manager=manager,
                    rag_system=rag_system,
                    course_id=course_id,
                    owner_user_id=owner_user_id,
                    source=source,
                    revision=revision,
                    material=material,
                )
            )
        except Exception as exc:  # one bad section must not discard the verified graph
            warnings.append(f"{material.get('title')}: {exc}")
        if progress:
            progress(60 + round(index / material_total * 35), "indexing", f"正在挂载节点资料 {index}/{material_total}")

    if not persisted:
        raise RuntimeError("教材节点资料全部入库失败，未替换现有知识图谱")
    graph["data"]["source_revision"] = revision
    graph["data"]["document_count"] = len(persisted)
    graph["data"]["warning_count"] = len(warnings)
    if not manager.save_knowledge_graph(course_id, graph):
        raise OSError("保存课程知识图谱失败")
    if progress:
        progress(98, "finalizing", "正在保存构建报告")
    return {
        "resource_type": "course_knowledge_base",
        "course_id": course_id,
        "source_id": source.source_id,
        "source_title": source.title,
        "source_url": source.landing_url,
        "source_license": source.license_name,
        "usage_restriction": source.usage_restriction or None,
        "source_revision": revision,
        "content_language": source.output_language,
        "chapter_count": len(graph["children"]),
        "node_document_count": len(persisted),
        "warning_count": len(warnings),
        "warnings": warnings[:50],
        "cleanup": report,
        "curricular_cleanup": curricular_cleanup,
        "built_at": utc_now(),
    }


def _material_quality(content: str, title: str) -> dict[str, Any]:
    text = str(content or "")
    visible = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    visible = re.sub(r"!\[[^\]]*\]\([^)]*\)|\[[^\]]+\]\([^)]*\)", " ", visible)
    visible = re.sub(r"[#>*_`|\-]+", " ", visible)
    visible = re.sub(r"\s+", " ", visible).strip()
    chinese_count = len(_CHINESE_RE.findall(visible))
    has_example = "```" in text or any(word in text for word in ("例如", "示例", "复杂度", "步骤"))
    excluded = any(
        word in str(title or "")
        for word in ("小结", "练习", "参考文献", "关于本书", "参与创作", "前言", "附录", "纸质书", "购买链接")
    )
    score = min(70, len(visible) // 18) + (20 if has_example else 0) + (10 if chinese_count >= 120 else 0)
    return {
        "score": min(100, score),
        "visible_chars": len(visible),
        "chinese_chars": chinese_count,
        "has_example": has_example,
        "needs_supplement": not excluded and len(visible) < 320 and score < 40,
    }


def _supplement_policy(url: str) -> dict[str, str] | None:
    host = urlparse(str(url or "")).netloc.casefold().split(":", 1)[0]
    for allowed_host, policy in SUPPLEMENTARY_SOURCE_POLICIES.items():
        if host == allowed_host or host.endswith(f".{allowed_host}"):
            if allowed_host == "docs.python.org" and "/zh-cn/" not in str(url):
                return None
            return {**policy, "host": allowed_host}
    return None


def _robots_allows(client: httpx.Client, url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = client.get(robots_url)
        if response.status_code >= 400:
            return True
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        return parser.can_fetch("EduAI-CourseKnowledgeBuilder/1.0", url)
    except Exception:
        return False


def _crawl_reviewed_supplement(client: httpx.Client, url: str) -> tuple[str, str]:
    policy = _supplement_policy(url)
    if policy is None:
        raise ValueError("补充来源不在审核白名单中")
    if not _robots_allows(client, url):
        raise PermissionError("来源 robots.txt 不允许抓取")
    response = client.get(url)
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").casefold()
    if "html" not in content_type:
        raise ValueError("补充来源不是可解析的网页正文")
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup.select("script, style, nav, header, footer, aside, form, noscript"):
        element.decompose()
    main = soup.select_one("main, article, [role='main'], .md-content, #content") or soup.body
    if main is None:
        raise ValueError("补充页面没有可识别的正文")
    title = str((soup.title.string if soup.title and soup.title.string else url)).strip()
    lines = [re.sub(r"\s+", " ", value).strip() for value in main.get_text("\n").splitlines()]
    content = "\n\n".join(value for value in lines if value)
    if len(content) < 500:
        raise ValueError("补充页面正文过短")
    return title, content[:40000]


def _persist_supplement(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    scope_id: str,
    topic: str,
    url: str,
    page_title: str,
    content: str,
) -> dict[str, Any]:
    policy = _supplement_policy(url)
    if policy is None:
        raise ValueError("补充来源不在审核白名单中")
    title = f"{topic}｜补充阅读：{page_title}"
    filename = _safe_material_filename("supplement", title, url)
    body = (
        f"# {title}\n\n"
        f"> 来源：[{policy['site_name']}]({url})  \n"
        f"> 许可：[{policy['license']}]({policy['license_url']})  \n"
        f"> 语言：{'简体中文' if policy['language'] == 'zh-CN' else '英文补充资料'}  \n"
        f"> 获取时间：{utc_now()}\n\n"
        f"{content}\n"
    )
    relative_path = manager.save_knowledge_base_file(
        course_id,
        body.encode("utf-8"),
        filename,
        scope_type="knowledge_point",
        scope_id=scope_id,
        library_type=LIBRARY_TYPE_COURSE,
    )
    if not relative_path:
        raise OSError("保存节点补充资料失败")
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
            "source_title": page_title,
            "source_domain": urlparse(url).netloc,
            "source_site_name": policy["site_name"],
            "source_license": policy["license"],
            "source_license_url": policy["license_url"],
            "source_language": policy["language"],
            "content_language": policy["language"],
            "translation_notice": "原文入库，未经过机器翻译",
            "authority_tier": "reviewed_supplementary_source",
            "generated_by": SUPPLEMENT_BUILDER_VERSION,
            "retrieved_at": utc_now(),
            "doc_kind": "web",
            "status": "ready",
            "chunk_count": int(import_result.get("chunk_count") or 0),
            "indexed_at": utc_now(),
        }
    )
    manager.save_knowledge_base_index(course_id, index)
    return {"document_id": record["id"], "scope_id": scope_id, "source_url": url}


def supplement_low_quality_nodes(
    *,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    max_nodes: int = 24,
) -> dict[str, Any]:
    """Audit generated leaf materials and supplement only weak nodes from reviewed sites."""
    from app.integrations.websearch import search_bocha
    from app.services.runtime_config_resolver import runtime_config_resolver

    course_dir = manager.get_course_dir(course_id).resolve()
    entries = manager.get_knowledge_base_index(course_id)
    existing_supplement_scopes = {
        str(item.get("scope_id") or "")
        for item in entries
        if item.get("generated_by") == SUPPLEMENT_BUILDER_VERSION
    }
    candidates: list[dict[str, Any]] = []
    for item in entries:
        if item.get("generated_by") != BUILDER_VERSION:
            continue
        path = (course_dir / str(item.get("path") or "")).resolve()
        try:
            path.relative_to(course_dir / "knowledge_base" / "documents")
        except ValueError:
            continue
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        quality = _material_quality(content, str(item.get("source_title") or item.get("filename") or ""))
        scope_id = str(item.get("scope_id") or "")
        if quality["needs_supplement"] and scope_id not in existing_supplement_scopes:
            candidates.append({**dict(item), "quality": quality})
    candidates.sort(key=lambda item: (item["quality"]["score"], item["quality"]["visible_chars"]))
    candidates = candidates[: max(0, min(int(max_nodes), 50))]

    runtime_search = runtime_config_resolver.resolve("web_search")
    api_key = str(runtime_search.get("api_key") or os.getenv("BOCHA_API_KEY", ""))
    base_url = str(runtime_search.get("base_url") or os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn"))
    if candidates and not api_key:
        raise RuntimeError("节点补充需要配置 BOCHA_API_KEY")

    supplemented: list[dict[str, Any]] = []
    failures: list[str] = []
    used_urls: set[str] = {
        str(item.get("source_url") or item.get("url") or "")
        for item in entries
        if item.get("generated_by") == SUPPLEMENT_BUILDER_VERSION
        and str(item.get("source_url") or item.get("url") or "")
    }
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        for item in candidates:
            topic = str(item.get("source_title") or item.get("filename") or "知识点")
            query = (
                f'"{topic}" (site:oi-wiki.org OR site:docs.python.org/zh-cn/ '
                "OR site:zh.wikipedia.org OR site:csunplugged.org/zh-hans/)"
            )
            try:
                curated_url = next(
                    (url for keyword, url in CURATED_SUPPLEMENT_URLS if keyword in topic and url not in used_urls),
                    None,
                )
                eligible_urls = [curated_url] if curated_url else []
                if not eligible_urls:
                    hits = search_bocha(
                        query,
                        count=8,
                        freshness="noLimit",
                        api_key=api_key,
                        base_url=base_url,
                        timeout=20,
                    )
                    eligible_urls = [
                        hit.url for hit in hits
                        if _supplement_policy(hit.url) and hit.url not in used_urls
                    ]
                if not eligible_urls:
                    english_query = f'"{topic}" computer science site:en.wikipedia.org'
                    hits = search_bocha(
                        english_query,
                        count=5,
                        freshness="noLimit",
                        api_key=api_key,
                        base_url=base_url,
                        timeout=20,
                    )
                    eligible_urls = [
                        hit.url for hit in hits
                        if _supplement_policy(hit.url) and hit.url not in used_urls
                    ]
                if not eligible_urls:
                    failures.append(f"{topic}: 未找到白名单来源")
                    continue
                selected_url = eligible_urls[0]
                page_title, content = _crawl_reviewed_supplement(client, selected_url)
                result = _persist_supplement(
                    manager=manager,
                    rag_system=rag_system,
                    course_id=course_id,
                    owner_user_id=owner_user_id,
                    scope_id=str(item.get("scope_id") or ""),
                    topic=topic,
                    url=selected_url,
                    page_title=page_title,
                    content=content,
                )
                supplemented.append(result)
                used_urls.add(selected_url)
            except Exception as exc:
                failures.append(f"{topic}: {exc}")
    return {
        "course_id": course_id,
        "audited_count": len(entries),
        "candidate_count": len(candidates),
        "supplemented_count": len(supplemented),
        "supplemented": supplemented,
        "failure_count": len(failures),
        "failures": failures,
        "completed_at": utc_now(),
    }


def submit_course_knowledge_build_job(
    *,
    course_id: str,
    owner_user_id: str,
    source_id: str,
    max_pages: int,
    clean_placeholders: bool,
) -> EduJob:
    job = create_job(
        kind=JobKind.BUILD_KNOWLEDGE_INDEX,
        owner_user_id=owner_user_id,
        course_id=course_id,
        input_summary={
            "source_id": source_id,
            "max_pages": max_pages,
            "clean_placeholders": clean_placeholders,
            "content_language": "zh-CN",
        },
    )
    from app.services.platform_task_handlers import enqueue_platform_task
    from app.services.runtime_config_resolver import runtime_config_resolver

    return enqueue_platform_task(
        job=job,
        workflow_type="course_knowledge_build",
        command={
            "course_id": course_id,
            "source_id": source_id,
            "max_pages": max_pages,
            "clean_placeholders": clean_placeholders,
        },
        runtime_config_snapshot=runtime_config_resolver.capture_snapshot(owner_user_id),
    )


def run_course_knowledge_build_job(
    *,
    job_id: str,
    manager: CourseStorageManager,
    rag_system: Any,
    course_id: str,
    owner_user_id: str,
    source_id: str,
    max_pages: int,
    clean_placeholders: bool,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, Any]:
    try:
        result = build_course_knowledge_base(
            manager=manager,
            rag_system=rag_system,
            course_id=course_id,
            owner_user_id=owner_user_id,
            source_id=source_id,
            max_pages=max_pages,
            clean_placeholders=clean_placeholders,
            progress=progress,
        )
        if progress:
            progress(98, "supplementing", "正在检查薄弱节点并检索权威补充资料")
        try:
            result["supplement"] = supplement_low_quality_nodes(
                manager=manager,
                rag_system=rag_system,
                course_id=course_id,
                owner_user_id=owner_user_id,
                max_nodes=24,
            )
        except Exception as supplement_exc:
            result["supplement"] = {
                "supplemented_count": 0,
                "failure_count": 1,
                "failures": [str(supplement_exc)],
            }
        update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="中文课程知识库构建完成",
            result_ref=result,
        )
        return result
    except Exception as exc:
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="failed",
            progress=100,
            message="中文课程知识库构建失败",
            error_code="COURSE_KB_BUILD_FAILED",
            error_message=str(exc),
        )
        raise
