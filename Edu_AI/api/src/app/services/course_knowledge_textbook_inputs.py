"""Stage and parse optional textbook inputs for a knowledge build draft."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import docx2txt

from app.integrations.pdf import get_pdf_parser
from app.persistence.dependencies import get_postgres_knowledge_repository
from app.persistence.postgres_knowledge_repository import (
    KnowledgeBuildRevisionConflict,
)
from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    update_job,
)
from app.services.runtime_config_resolver import runtime_config_resolver


SUPPORTED_TEXTBOOK_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_TEXTBOOK_BYTES = 50 * 1024 * 1024
MAX_PARSE_CHUNKS = 160
PARSE_CHUNK_CHARS = 6000


class CourseKnowledgeTextbookInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _safe_filename(filename: str) -> tuple[str, str]:
    normalized = Path(str(filename or "")).name
    suffix = Path(normalized).suffix.lower()
    if suffix not in SUPPORTED_TEXTBOOK_EXTENSIONS:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_FORMAT_UNSUPPORTED",
            "教材仅支持 PDF、DOCX、TXT 和 Markdown 文件",
        )
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", Path(normalized).stem)
    stem = stem.strip("-._")[:100] or "textbook"
    return f"{stem}{suffix}", suffix


def _get_build(repository: Any, *, course_id: str, build_id: str) -> dict[str, Any]:
    build = repository.get_build(build_id)
    if build is None or str(build.get("library_id") or "") != course_id:
        raise CourseKnowledgeTextbookInputError(
            "KNOWLEDGE_BUILD_NOT_FOUND", "知识库构建草案不存在"
        )
    if build.get("status") != "draft":
        raise CourseKnowledgeTextbookInputError(
            "KNOWLEDGE_BUILD_NOT_EDITABLE", "只有草案状态可以修改教材输入"
        )
    return build


def stage_course_knowledge_textbook(
    *,
    manager: Any,
    course_id: str,
    build_id: str,
    owner_user_id: str,
    expected_revision: int,
    filename: str,
    file_bytes: bytes,
    repository: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repository = repository or get_postgres_knowledge_repository()
    build = _get_build(repository, course_id=course_id, build_id=build_id)
    if int(build.get("revision") or 0) != int(expected_revision):
        raise KnowledgeBuildRevisionConflict(
            f"构建草案版本冲突：当前 {build.get('revision')}，提交 {expected_revision}"
        )
    safe_filename, suffix = _safe_filename(filename)
    payload = bytes(file_bytes or b"")
    if not payload:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_EMPTY", "上传的教材文件为空"
        )
    if len(payload) > MAX_TEXTBOOK_BYTES:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_TOO_LARGE", "单个教材文件不能超过 50 MB"
        )
    content_hash = hashlib.sha256(payload).hexdigest()
    textbooks = [dict(item) for item in build.get("textbooks") or []]
    duplicate = next(
        (
            item
            for item in textbooks
            if str(item.get("content_hash") or "") == content_hash
        ),
        None,
    )
    if duplicate:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_DUPLICATE",
            f"当前构建已上传相同教材：{duplicate.get('filename') or safe_filename}",
        )
    textbook_id = f"textbook-{uuid4().hex}"
    course_root = Path(manager.get_course_dir(course_id)).resolve()
    target_dir = (
        course_root / "knowledge_build_inputs" / build_id / textbook_id
    ).resolve()
    try:
        target_dir.relative_to(course_root)
    except ValueError as exc:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_PATH_INVALID", "教材暂存路径非法"
        ) from exc
    target_dir.mkdir(parents=True, exist_ok=False)
    target_path = target_dir / f"original{suffix}"
    target_path.write_bytes(payload)
    relative_path = target_path.relative_to(course_root).as_posix()
    textbook = {
        "textbook_id": textbook_id,
        "filename": safe_filename,
        "extension": suffix,
        "size_bytes": len(payload),
        "content_hash": content_hash,
        "relative_path": relative_path,
        "status": "queued",
        "uploaded_by": str(owner_user_id or ""),
        "uploaded_at": _now_iso(),
        "parse_result": None,
        "error": None,
    }
    textbooks.append(textbook)
    try:
        updated = repository.update_build_draft(
            build_id,
            expected_revision=expected_revision,
            changes={"textbooks": textbooks},
            phase="textbook_parsing",
        )
    except Exception:
        # The immutable file is intentionally retained for diagnosis/recovery.
        raise
    return updated, textbook


def _decode_text(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CourseKnowledgeTextbookInputError(
        "TEXTBOOK_ENCODING_UNSUPPORTED", "无法识别教材文本编码"
    )


def _parse_markdown_bytes(
    *,
    path: Path,
    filename: str,
    pdf_parser: Any | None = None,
) -> tuple[str, str, list[str]]:
    suffix = path.suffix.lower()
    warnings: list[str] = []
    if suffix in {".txt", ".md"}:
        text = _decode_text(path.read_bytes())
        return text, "markdown" if suffix == ".md" else "text", warnings
    if suffix == ".docx":
        text = str(docx2txt.process(str(path)) or "").strip()
        if not text:
            raise CourseKnowledgeTextbookInputError(
                "TEXTBOOK_PARSE_EMPTY", "DOCX 教材没有提取到可读文本"
            )
        return text, "docx2txt", warnings
    if suffix == ".pdf":
        parser = pdf_parser or get_pdf_parser()
        parsed = parser.parse(path.read_bytes(), filename=filename)
        text = str(parsed.text or "").strip()
        if not text:
            raise CourseKnowledgeTextbookInputError(
                "TEXTBOOK_PARSE_EMPTY", "MinerU 没有从 PDF 教材提取到正文"
            )
        page_count = (parsed.metadata or {}).get("pageCount")
        if page_count is None:
            warnings.append("PDF 解析结果未提供页数")
        return text, str((parsed.metadata or {}).get("parser") or "mineru"), warnings
    raise CourseKnowledgeTextbookInputError(
        "TEXTBOOK_FORMAT_UNSUPPORTED", "不支持的教材格式"
    )


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_PAGE_RE = re.compile(r"^#\s*page\s+(\d+)\s*$", re.IGNORECASE)


def _extract_outline_and_chunks(
    markdown: str,
    *,
    textbook_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    lines = str(markdown or "").splitlines()
    headings: list[dict[str, Any]] = []
    current_page: int | None = None
    for index, line in enumerate(lines):
        page_match = _PAGE_RE.match(line.strip())
        if page_match:
            current_page = int(page_match.group(1))
            continue
        match = _HEADING_RE.match(line.strip())
        if not match:
            continue
        title = _clean(match.group(2))
        if not title:
            continue
        headings.append(
            {
                "title": title,
                "level": len(match.group(1)),
                "line_index": index,
                "page": current_page,
            }
        )
    warnings: list[str] = []
    if headings:
        top_level = min(item["level"] for item in headings)
        chapter_candidates = [item for item in headings if item["level"] == top_level]
    else:
        chapter_candidates = []
        warnings.append("未识别到明确标题，已把全文作为一个章节样本")
    if not chapter_candidates:
        chapter_candidates = [
            {"title": "教材正文", "level": 1, "line_index": 0, "page": 1}
        ]
    outline: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for chapter_index, chapter in enumerate(chapter_candidates):
        start = int(chapter["line_index"])
        end = (
            int(chapter_candidates[chapter_index + 1]["line_index"])
            if chapter_index + 1 < len(chapter_candidates)
            else len(lines)
        )
        chapter_id = f"{textbook_id}-chapter-{chapter_index + 1}"
        sections = [
            {
                "id": f"{chapter_id}-section-{section_index + 1}",
                "title": item["title"],
                "level": item["level"],
                "line_index": item["line_index"],
                "page": item.get("page"),
            }
            for section_index, item in enumerate(
                entry
                for entry in headings
                if start < int(entry["line_index"]) < end
            )
        ]
        outline.append(
            {
                "id": chapter_id,
                "title": chapter["title"],
                "level": chapter["level"],
                "line_index": start,
                "page": chapter.get("page"),
                "sections": sections[:80],
            }
        )
        content = "\n".join(lines[start:end]).strip()
        for offset in range(0, max(1, len(content)), PARSE_CHUNK_CHARS):
            if len(chunks) >= MAX_PARSE_CHUNKS:
                warnings.append(f"正文块超过 {MAX_PARSE_CHUNKS} 个，已截断模型输入样本")
                break
            value = content[offset : offset + PARSE_CHUNK_CHARS].strip()
            if not value:
                continue
            chunk_index = len(chunks) + 1
            chunks.append(
                {
                    "chunk_id": f"{textbook_id}-chunk-{chunk_index}",
                    "chapter_id": chapter_id,
                    "chapter_title": chapter["title"],
                    "page": chapter.get("page"),
                    "content": value,
                    "content_hash": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                }
            )
    return outline, chunks, warnings


def parse_course_knowledge_textbook(
    *,
    path: Path,
    filename: str,
    textbook_id: str,
    pdf_parser: Any | None = None,
) -> dict[str, Any]:
    markdown, parser_used, warnings = _parse_markdown_bytes(
        path=path,
        filename=filename,
        pdf_parser=pdf_parser,
    )
    outline, chunks, structure_warnings = _extract_outline_and_chunks(
        markdown,
        textbook_id=textbook_id,
    )
    plain = _clean(re.sub(r"^#{1,6}\s+", "", markdown, flags=re.MULTILINE))
    return {
        "parser": parser_used,
        "summary": plain[:4000],
        "outline": outline,
        "chunks": chunks,
        "char_count": len(markdown),
        "chapter_count": len(outline),
        "chunk_count": len(chunks),
        "warnings": [*warnings, *structure_warnings],
        "parsed_at": _now_iso(),
    }


def _mutate_textbook(
    repository: Any,
    *,
    course_id: str,
    build_id: str,
    textbook_id: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
    phase: str,
) -> dict[str, Any]:
    for _attempt in range(4):
        build = _get_build(repository, course_id=course_id, build_id=build_id)
        revision = int(build.get("revision") or 0)
        textbooks = [dict(item) for item in build.get("textbooks") or []]
        found = False
        for index, item in enumerate(textbooks):
            if str(item.get("textbook_id") or "") == textbook_id:
                textbooks[index] = mutate(item)
                found = True
                break
        if not found:
            raise CourseKnowledgeTextbookInputError(
                "TEXTBOOK_NOT_FOUND", "教材输入不存在或已移除"
            )
        try:
            return repository.update_build_draft(
                build_id,
                expected_revision=revision,
                changes={"textbooks": textbooks},
                phase=phase,
            )
        except KnowledgeBuildRevisionConflict:
            continue
    raise KnowledgeBuildRevisionConflict("教材解析结果写入时构建草案持续发生冲突")


def submit_course_knowledge_textbook_parse_job(
    *,
    course_id: str,
    owner_user_id: str,
    build_id: str,
    textbook_id: str,
) -> EduJob:
    job = create_job(
        kind=JobKind.PARSE_DOCUMENT,
        owner_user_id=owner_user_id,
        course_id=course_id,
        scope_type="knowledge_build",
        scope_id=build_id,
        input_summary={"build_id": build_id, "textbook_id": textbook_id},
    )
    from app.services.platform_task_handlers import enqueue_platform_task

    return enqueue_platform_task(
        job=job,
        workflow_type="course_knowledge_textbook_parse",
        command={
            "course_id": course_id,
            "build_id": build_id,
            "textbook_id": textbook_id,
            "deadline_seconds": 900,
        },
        runtime_config_snapshot=runtime_config_resolver.capture_snapshot(
            owner_user_id
        ),
    )


def run_course_knowledge_textbook_parse_job(
    *,
    manager: Any,
    job_id: str,
    course_id: str,
    build_id: str,
    textbook_id: str,
    progress: Callable[[int, str, str], None] | None = None,
    repository: Any | None = None,
    pdf_parser: Any | None = None,
) -> dict[str, Any]:
    repository = repository or get_postgres_knowledge_repository()
    build = _get_build(repository, course_id=course_id, build_id=build_id)
    textbook = next(
        (
            dict(item)
            for item in build.get("textbooks") or []
            if str(item.get("textbook_id") or "") == textbook_id
        ),
        None,
    )
    if textbook is None:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_NOT_FOUND", "教材输入不存在"
        )
    try:
        _mutate_textbook(
            repository,
            course_id=course_id,
            build_id=build_id,
            textbook_id=textbook_id,
            mutate=lambda item: {**item, "status": "parsing", "error": None},
            phase="textbook_parsing",
        )
        if progress:
            progress(10, "textbook_parsing", f"正在解析教材 {textbook.get('filename')}")
        course_root = Path(manager.get_course_dir(course_id)).resolve()
        source_path = (course_root / str(textbook.get("relative_path") or "")).resolve()
        try:
            source_path.relative_to(course_root)
        except ValueError as exc:
            raise CourseKnowledgeTextbookInputError(
                "TEXTBOOK_PATH_INVALID", "教材路径超出课程目录"
            ) from exc
        if not source_path.is_file():
            raise CourseKnowledgeTextbookInputError(
                "TEXTBOOK_FILE_MISSING", "教材原文件不存在"
            )
        parse_result = parse_course_knowledge_textbook(
            path=source_path,
            filename=str(textbook.get("filename") or source_path.name),
            textbook_id=textbook_id,
            pdf_parser=pdf_parser,
        )
        if progress:
            progress(85, "textbook_structuring", "正在保存教材目录和正文块")
        updated = _mutate_textbook(
            repository,
            course_id=course_id,
            build_id=build_id,
            textbook_id=textbook_id,
            mutate=lambda item: {
                **item,
                "status": "ready",
                "parse_result": parse_result,
                "error": None,
            },
            phase="draft_config",
        )
        result = {
            "course_id": course_id,
            "build_id": build_id,
            "textbook_id": textbook_id,
            "revision": updated["revision"],
            "chapter_count": parse_result["chapter_count"],
            "chunk_count": parse_result["chunk_count"],
        }
        update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            step="textbook_ready",
            progress=100,
            message="教材解析完成",
            result_ref=result,
        )
        return result
    except Exception as exc:
        error_code = getattr(exc, "code", "TEXTBOOK_PARSE_FAILED")
        try:
            _mutate_textbook(
                repository,
                course_id=course_id,
                build_id=build_id,
                textbook_id=textbook_id,
                mutate=lambda item: {
                    **item,
                    "status": "failed",
                    "error": {"code": error_code, "message": str(exc)},
                },
                phase="draft_config",
            )
        except Exception:
            pass
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="textbook_parse_failed",
            progress=100,
            message="教材解析失败",
            error_code=str(error_code),
            error_message=str(exc),
        )
        raise


def remove_course_knowledge_textbook(
    *,
    course_id: str,
    build_id: str,
    textbook_id: str,
    expected_revision: int,
    repository: Any | None = None,
) -> dict[str, Any]:
    repository = repository or get_postgres_knowledge_repository()
    build = _get_build(repository, course_id=course_id, build_id=build_id)
    if int(build.get("revision") or 0) != int(expected_revision):
        raise KnowledgeBuildRevisionConflict("移除教材时构建草案版本冲突")
    textbooks = [
        dict(item)
        for item in build.get("textbooks") or []
        if str(item.get("textbook_id") or "") != textbook_id
    ]
    if len(textbooks) == len(build.get("textbooks") or []):
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_NOT_FOUND", "教材输入不存在"
        )
    return repository.update_build_draft(
        build_id,
        expected_revision=expected_revision,
        changes={"textbooks": textbooks},
        phase="draft_config",
    )


def retry_course_knowledge_textbook(
    *,
    course_id: str,
    build_id: str,
    textbook_id: str,
    expected_revision: int,
    repository: Any | None = None,
) -> dict[str, Any]:
    repository = repository or get_postgres_knowledge_repository()
    build = _get_build(repository, course_id=course_id, build_id=build_id)
    if int(build.get("revision") or 0) != int(expected_revision):
        raise KnowledgeBuildRevisionConflict("重试教材解析时构建草案版本冲突")
    textbooks = [dict(item) for item in build.get("textbooks") or []]
    found = False
    for index, item in enumerate(textbooks):
        if str(item.get("textbook_id") or "") == textbook_id:
            textbooks[index] = {**item, "status": "queued", "error": None}
            found = True
            break
    if not found:
        raise CourseKnowledgeTextbookInputError(
            "TEXTBOOK_NOT_FOUND", "教材输入不存在"
        )
    return repository.update_build_draft(
        build_id,
        expected_revision=expected_revision,
        changes={"textbooks": textbooks},
        phase="textbook_parsing",
    )
