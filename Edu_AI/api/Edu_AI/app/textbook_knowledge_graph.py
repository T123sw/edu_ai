from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx2txt
import requests
from dotenv import dotenv_values

from core.course_storage import CourseStorageManager


class TextbookKnowledgeGraphError(RuntimeError):
    """Raised when the textbook import pipeline cannot complete."""


_CHAPTER_LINE_RE = re.compile(
    r"^(?:#{1,2}\s+.+|\u7b2c[\d\u4e00-\u9fff\u96f6\u4e24]+\u7ae0[^\n]*|chapter\s+\d+[^\n]*|\d+\s*[.\u3001]\s*.+)$",
    re.IGNORECASE,
)
_SECTION_LINE_RE = re.compile(
    r"^(?:#{2,4}\s+.+|\d+(?:\.\d+){1,3}\s*.+|\(?[\u4e00-\u9fff]{1,3}\)?[\u3001.\uff0e]\s*.+)$",
    re.IGNORECASE,
)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_PAGE_HEADING_RE = re.compile(r"^page\s+\d+$", re.IGNORECASE)
_NUMERIC_PREFIX_RE = re.compile(r"^(?:chapter\s+)?(\d+(?:\.\d+)*)", re.IGNORECASE)
_CHINESE_CHAPTER_PREFIX_RE = re.compile(r"^第[\d\u4e00-\u9fff\u96f6\u4e24]+\u7ae0")
_LOCAL_CHAPTER_TITLE_RE = re.compile(
    r"^(?:第[\d\u4e00-\u9fff\u96f6\u4e24]+\u7ae0\s*.+|chapter\s+\d+\b.*)$",
    re.IGNORECASE,
)
_LOCAL_SECTION_TITLE_RE = re.compile(r"^\d+\.\d+\s*.+$")


def _workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "new_project").exists() and (parent / "edu_ai_src").exists():
            return parent
    return Path.cwd()


def _default_external_env_path() -> Path:
    return _workspace_root() / "edu_ai_src" / "edu_ai-main" / "Edu_AI" / "api" / "Edu_AI" / ".env"


def _default_llm_env_paths() -> List[Path]:
    current = Path(__file__).resolve()
    candidates = [
        current.parents[1] / ".env",
        current.parents[3] / ".env",
        _default_external_env_path(),
    ]
    unique_candidates: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate.resolve(strict=False))
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def _normalize_slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip()).strip("._-")
    return cleaned or fallback


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_for_compare(value: str) -> str:
    lowered = _normalize_whitespace(value).lower()
    return re.sub(r"[\W_]+", "", lowered)


def _clean_outline_title(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    if text.startswith("#"):
        level = len(text) - len(text.lstrip("#"))
        text = text[level:].strip()

    text = text.replace("\\*", "").replace("*", "")
    text = text.replace("\\_", "_")
    text = text.replace("•", " ").replace("●", " ")
    text = re.sub(r"^[>\-+\s]+", "", text)
    text = re.sub(r"[·.…]{2,}", " ", text)
    text = _normalize_whitespace(text)
    text = re.sub(r"(?<=\D)\d{1,4}\s*$", "", text)
    text = re.sub(r"[·.…\s]+$", "", text)
    return _normalize_whitespace(text)


def _has_outline_title_text(title: str) -> bool:
    if _is_page_heading(title):
        return False
    body = _strip_title_prefix(title)
    meaningful = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", body)
    if not meaningful:
        return False
    if re.search(r"[\u4e00-\u9fff]", meaningful):
        return len(meaningful) >= 1
    return len(meaningful) >= 2


def _parse_chapter_number(value: str) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    digits = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if "十" in text:
        left, _, right = text.partition("十")
        if left and left not in digits:
            return None
        if right and right not in digits:
            return None
        tens = digits.get(left, 1) if left else 1
        ones = digits.get(right, 0) if right else 0
        return tens * 10 + ones

    total = 0
    for char in text:
        if char not in digits:
            return None
        total = total * 10 + digits[char]
    return total


def _extract_chapter_number(title: str) -> Optional[int]:
    cleaned = _clean_outline_title(title)
    chapter_match = re.match(r"^第([\d\u4e00-\u9fff\u96f6\u4e24]+)章", cleaned)
    if chapter_match:
        return _parse_chapter_number(chapter_match.group(1))

    chapter_match = re.match(r"^chapter\s+(\d+)\b", cleaned, re.IGNORECASE)
    if chapter_match:
        return int(chapter_match.group(1))

    prefix = _extract_numeric_prefix(cleaned)
    if prefix and "." not in prefix and prefix.isdigit():
        return int(prefix)

    return None


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_pdf_text_with_pymupdf(path: Path) -> str:
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on runtime install
        raise TextbookKnowledgeGraphError("PyMuPDF unavailable and MinerU parsing failed.") from exc

    blocks: List[str] = []
    document = fitz.open(str(path))
    try:
        for page_index in range(len(document)):
            page = document.load_page(page_index)
            text = str(page.get_text("text") or "").strip()
            if not text:
                continue
            blocks.append(f"# Page {page_index + 1}\n\n{text}")
    finally:
        document.close()

    merged = "\n\n".join(blocks).strip()
    if not merged:
        raise TextbookKnowledgeGraphError(f"No readable text extracted from PDF: {path.name}")
    return merged


def _ensure_markdown_title(text: str, title: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return f"# {title}\n"
    if stripped.startswith("#"):
        return stripped
    return f"# {title}\n\n{stripped}"


def _resolve_llm_env_values(explicit_env_path: Optional[str] = None) -> tuple[Dict[str, str], Path]:
    candidates: List[Path] = []
    if explicit_env_path:
        candidates.append(Path(explicit_env_path))
    env_from_var = str(os.getenv("TEXTBOOK_PIPELINE_ENV_PATH") or "").strip()
    if env_from_var:
        candidates.append(Path(env_from_var))
    candidates.extend(_default_llm_env_paths())

    for candidate in candidates:
        if candidate.exists():
            values = {
                key: str(value or "").strip()
                for key, value in dotenv_values(candidate).items()
                if key
            }
            return values, candidate

    raise TextbookKnowledgeGraphError(
        f"LLM env file not found. Checked: {', '.join(str(path) for path in candidates)}"
    )


def _normalize_openai_base_url(value: str) -> str:
    base = str(value or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/v1") or base.endswith("/api/v1"):
        return base
    return f"{base}/v1"


def _pick_first(values: Dict[str, str], keys: List[str]) -> str:
    for key in keys:
        value = str(values.get(key) or os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def _resolve_openai_compatible_config(explicit_env_path: Optional[str] = None) -> Dict[str, str]:
    values, env_path = _resolve_llm_env_values(explicit_env_path)
    candidates = [
        {
            "label": "ppt_llm",
            "base": ["PPT_LLM_API_BASE"],
            "key": ["PPT_LLM_API_KEY"],
            "model": ["PPT_LLM_MODEL"],
        },
        {
            "label": "answer_llm",
            "base": ["ANSWER_LLM_API_BASE", "QWEN_BASE_URL"],
            "key": ["ANSWER_LLM_API_KEY", "QWEN_API_KEY"],
            "model": ["ANSWER_LLM_MODEL", "VISION_MODEL_ID"],
        },
        {
            "label": "qwen",
            "base": ["QWEN_BASE_URL"],
            "key": ["QWEN_API_KEY"],
            "model": ["VISION_MODEL_ID"],
        },
        {
            "label": "deepseek",
            "base": ["DEEPSEEK_BASE_URL"],
            "key": ["DEEPSEEK_API_KEY"],
            "model": ["LLM_MODEL_DEEP"],
        },
        {
            "label": "openrouter",
            "base": ["OPENROUTER_BASE_URL"],
            "key": ["OPENROUTER_API_KEY"],
            "model": ["LOGIC_MODEL_MINI"],
        },
    ]

    for candidate in candidates:
        api_base = _normalize_openai_base_url(_pick_first(values, candidate["base"]))
        api_key = _pick_first(values, candidate["key"])
        model = _pick_first(values, candidate["model"])
        if api_base and api_key and model:
            return {
                "provider": candidate["label"],
                "api_base": api_base,
                "api_key": api_key,
                "model": model,
                "env_path": str(env_path),
            }

    raise TextbookKnowledgeGraphError(f"No usable OpenAI-compatible config found in {env_path}")


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise TextbookKnowledgeGraphError("LLM returned empty content.")

    fenced = _JSON_BLOCK_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    else:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            text = text[first : last + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TextbookKnowledgeGraphError(f"Failed to parse LLM JSON output: {exc}") from exc

    if not isinstance(parsed, dict):
        raise TextbookKnowledgeGraphError("LLM output is not a JSON object.")
    return parsed


def _invoke_outline_model(*, payload: Dict[str, Any], explicit_env_path: Optional[str] = None) -> Dict[str, Any]:
    config = _resolve_openai_compatible_config(explicit_env_path)
    system_prompt = (
        "You reconstruct a textbook table of contents from parsed textbook markdown. "
        "Split the textbook by every real directory node, preserve the original order, "
        "and return JSON only."
    )
    user_prompt = (
        "Read the parsed textbook input carefully before deciding any split.\n"
        "You must first study the first 20 pages in detail, especially directory pages, table-of-contents pages, preface pages, and the earliest chapter openings.\n"
        "Use those first 20 pages to understand the textbook's true directory hierarchy and naming style.\n"
        "After that, reconstruct the real directory tree from the full textbook.\n"
        "Then return a chapter/section structure for every real directory node.\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "course_title": "string",\n'
        '  "summary": "string",\n'
        '  "chapters": [\n'
        "    {\n"
        '      "title": "string",\n'
        '      "summary": "string",\n'
        '      "sections": [\n'
        "        {\n"
        '          "title": "string",\n'
        '          "summary": "string",\n'
        '          "concepts": ["string"]\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Treat the first 20 pages as the strongest evidence for how the directory should be split.\n"
        "- If a table of contents appears in the first 20 pages, use it as the primary split basis and verify against the body text.\n"
        "- Use the TOC only to reconstruct chapter and section hierarchy; never use TOC lines themselves as chapter content boundaries.\n"
        "- Every chapter and section boundary must correspond to a real body-text heading in the textbook, not a directory entry.\n"
        "- If body text and TOC conflict, prefer the TOC naming and ordering from the first 20 pages unless the body clearly proves the TOC is wrong.\n"
        "- Use titles exactly as they appear in the parsed textbook whenever possible.\n"
        "- Split by every real directory node, not by page markers and not by arbitrary page spans.\n"
        "- Ignore page headings such as 'Page 12'.\n"
        "- Ignore copyright pages, ISBN lines, page numbers, broken numeric fragments, and repeated TOC duplicates.\n"
        "- Keep chapter and section order aligned with the textbook.\n"
        "- Do not invent chapters or sections not supported by the input.\n"
        "- Each section should contain 2 to 6 concise concepts.\n"
        "- No markdown fences, no explanation, JSON only.\n\n"
        f"Parsed textbook input:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    response = requests.post(
        f"{config['api_base']}/chat/completions",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=180,
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise TextbookKnowledgeGraphError("LLM response did not contain choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(
            str(item.get("text") or "").strip()
            for item in content
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )
    parsed = _extract_json_object(str(content or ""))
    parsed["_provider"] = config["provider"]
    parsed["_env_path"] = config["env_path"]
    return parsed


def _classify_heading(line: str) -> Optional[Dict[str, Any]]:
    stripped = str(line or "").strip()
    if not stripped:
        return None

    if stripped.startswith("#"):
        level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[level:].strip().strip("#").strip()
        if not title:
            return None
        role = "chapter" if level == 1 else "section"
        return {"title": title, "level": level, "role": role}

    if _CHAPTER_LINE_RE.match(stripped):
        return {"title": stripped, "level": 1, "role": "chapter"}

    if _SECTION_LINE_RE.match(stripped):
        return {"title": stripped, "level": 2, "role": "section"}

    return None


def _is_page_heading(title: str) -> bool:
    return bool(_PAGE_HEADING_RE.match(_normalize_whitespace(title)))


def _strip_title_prefix(title: str) -> str:
    text = _normalize_whitespace(title)
    text = _CHINESE_CHAPTER_PREFIX_RE.sub("", text)
    text = re.sub(r"^chapter\s+\d+\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d+(?:\.\d+)*\s*[-.\u3001:：)]*\s*", "", text)
    return _normalize_whitespace(text)


def _has_substantive_title_text(title: str) -> bool:
    if _is_page_heading(title):
        return False
    body = _strip_title_prefix(title)
    meaningful = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", body)
    return len(meaningful) >= 2


def _extract_numeric_prefix(title: str) -> str:
    text = _normalize_whitespace(title)
    match = _NUMERIC_PREFIX_RE.match(text)
    if match:
        return match.group(1)
    return ""


def _extract_outline_candidates(markdown_text: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for line_index, line in enumerate(markdown_text.splitlines()):
        info = _classify_heading(line)
        if not info:
            continue
        title = _normalize_whitespace(str(info["title"] or ""))
        if not title or not _has_substantive_title_text(title):
            continue
        signature = (_normalize_for_compare(title), str(info["role"]), line_index)
        if signature in seen:
            continue
        seen.add(signature)
        candidates.append(
            {
                "title": title,
                "role": str(info["role"]),
                "level": int(info["level"]),
                "line_index": line_index,
            }
        )
    return candidates


def _extract_first_page_window(markdown_text: str, page_limit: int = 20) -> str:
    text = str(markdown_text or "").strip()
    if not text:
        return ""

    pattern = re.compile(r"(?im)^#\s*page\s+(\d+)\s*$")
    matches = list(pattern.finditer(text))
    if not matches:
        return text[:16000]

    collected: List[str] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        if page_number > page_limit:
            break
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        collected.append(text[start:end].strip())

    preview = "\n\n".join(item for item in collected if item).strip()
    return preview[:20000]


def _summarize_text(text: str, max_chars: int = 160) -> str:
    plain = _normalize_whitespace(
        re.sub(r"^#{1,6}\s+", "", str(text or ""), flags=re.MULTILINE)
    )
    if len(plain) <= max_chars:
        return plain
    return plain[: max_chars - 3].rstrip() + "..."


def _normalize_concepts(raw_concepts: Any) -> List[str]:
    concepts: List[str] = []
    for item in raw_concepts if isinstance(raw_concepts, list) else []:
        concept = _normalize_whitespace(str(item or ""))
        if concept and concept not in concepts:
            concepts.append(concept)
    return concepts[:6]


def _normalize_outline_from_llm(*, course_title: str, outline: Dict[str, Any]) -> Dict[str, Any]:
    llm_chapters = outline.get("chapters")
    if not isinstance(llm_chapters, list):
        llm_chapters = []

    normalized_chapters: List[Dict[str, Any]] = []
    for chapter in llm_chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_title = _normalize_whitespace(str(chapter.get("title") or ""))
        if not chapter_title or not _has_substantive_title_text(chapter_title):
            continue

        normalized_sections: List[Dict[str, Any]] = []
        for section in chapter.get("sections") if isinstance(chapter.get("sections"), list) else []:
            if not isinstance(section, dict):
                continue
            section_title = _normalize_whitespace(str(section.get("title") or ""))
            if not section_title or not _has_substantive_title_text(section_title):
                continue
            normalized_sections.append(
                {
                    "title": section_title,
                    "summary": _normalize_whitespace(str(section.get("summary") or "")),
                    "concepts": _normalize_concepts(section.get("concepts")),
                }
            )

        normalized_chapters.append(
            {
                "title": chapter_title,
                "summary": _normalize_whitespace(str(chapter.get("summary") or "")),
                "sections": normalized_sections,
            }
        )

    if not normalized_chapters:
        raise TextbookKnowledgeGraphError("LLM did not return usable textbook directory nodes.")

    return {
        "course_title": _normalize_whitespace(str(outline.get("course_title") or course_title)) or course_title,
        "summary": _normalize_whitespace(
            str(outline.get("summary") or f"{course_title} textbook knowledge graph")
        ),
        "chapters": normalized_chapters,
        "outline_source": str(outline.get("_provider") or "llm"),
        "env_path": str(outline.get("_env_path") or ""),
        "_provider": str(outline.get("_provider") or "llm"),
        "_env_path": str(outline.get("_env_path") or ""),
    }


def _outline_role_from_title(title: str, *, markdown_level: Optional[int] = None) -> Optional[str]:
    cleaned = _clean_outline_title(title)
    if not cleaned or not _has_outline_title_text(cleaned):
        return None

    if _LOCAL_CHAPTER_TITLE_RE.match(cleaned):
        return "chapter"

    if _LOCAL_SECTION_TITLE_RE.match(cleaned):
        prefix = _extract_numeric_prefix(cleaned)
        if prefix.count(".") == 1:
            return "section"
        return None

    prefix = _extract_numeric_prefix(cleaned)
    if prefix and prefix.count(".") == 1:
        return "section"

    if markdown_level == 1:
        return "chapter"

    return None


def _build_outline_from_entries(
    *,
    course_title: str,
    entries: List[Dict[str, str]],
    outline_source: str,
) -> Optional[Dict[str, Any]]:
    chapters: List[Dict[str, Any]] = []
    current_chapter: Optional[Dict[str, Any]] = None
    chapter_signatures: set[str] = set()

    for entry in entries:
        role = str(entry.get("role") or "").strip()
        title = _clean_outline_title(str(entry.get("title") or ""))
        if role not in {"chapter", "section"} or not title:
            continue

        if role == "chapter":
            signature = _normalize_for_compare(title)
            if not signature or signature in chapter_signatures:
                current_chapter = chapters[-1] if chapters else None
                continue
            current_chapter = {"title": title, "summary": "", "sections": []}
            chapters.append(current_chapter)
            chapter_signatures.add(signature)
            continue

        if current_chapter is None:
            continue

        section_signatures = {
            _normalize_for_compare(str(section.get("title") or ""))
            for section in current_chapter["sections"]
            if isinstance(section, dict)
        }
        signature = _normalize_for_compare(title)
        if not signature or signature in section_signatures:
            continue

        current_chapter["sections"].append(
            {
                "title": title,
                "summary": "",
                "concepts": [],
            }
        )

    if not chapters:
        return None

    return {
        "course_title": course_title,
        "summary": f"{course_title} textbook knowledge graph",
        "chapters": chapters,
        "outline_source": outline_source,
        "env_path": "",
    }


def _extract_local_outline_from_toc(*, markdown_text: str, course_title: str) -> Optional[Dict[str, Any]]:
    lines = markdown_text.splitlines()
    toc_start: Optional[int] = None

    for line_index, line in enumerate(lines[: min(len(lines), 400)]):
        if _normalize_for_compare(_clean_outline_title(line)) in {"目录", "contents", "tableofcontents"}:
            toc_start = line_index
            break

    if toc_start is None:
        return None

    entries: List[Dict[str, str]] = []
    found_entry = False
    noise_run = 0
    last_chapter_number: Optional[int] = None

    for raw_line in lines[toc_start + 1 : min(len(lines), toc_start + 700)]:
        title = _clean_outline_title(raw_line)
        if not title:
            continue

        role = _outline_role_from_title(title)
        if role is None:
            if found_entry:
                noise_run += 1
                if noise_run >= 10:
                    break
            continue

        found_entry = True
        noise_run = 0
        if role == "chapter":
            chapter_number = _extract_chapter_number(title)
            if (
                chapter_number is not None
                and last_chapter_number is not None
                and chapter_number <= last_chapter_number
            ):
                break
            if chapter_number is not None:
                last_chapter_number = chapter_number
        entries.append({"title": title, "role": role})

    outline = _build_outline_from_entries(
        course_title=course_title,
        entries=entries,
        outline_source="local_toc",
    )
    if outline and len(outline["chapters"]) >= 2:
        return outline
    return outline


def _extract_local_outline_from_headings(*, markdown_text: str, course_title: str) -> Optional[Dict[str, Any]]:
    entries: List[Dict[str, str]] = []

    for line in markdown_text.splitlines():
        stripped = str(line or "").strip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        title = _clean_outline_title(stripped)
        role = _outline_role_from_title(title, markdown_level=level)
        if role is None:
            continue
        entries.append({"title": title, "role": role})

    return _build_outline_from_entries(
        course_title=course_title,
        entries=entries,
        outline_source="local_headings",
    )


def _extract_local_outline_from_candidates(*, markdown_text: str, course_title: str) -> Optional[Dict[str, Any]]:
    entries: List[Dict[str, str]] = []

    for candidate in _extract_outline_candidates(markdown_text):
        title = _clean_outline_title(str(candidate.get("title") or ""))
        role = _outline_role_from_title(title, markdown_level=int(candidate.get("level") or 0))
        if role is None:
            continue
        entries.append({"title": title, "role": role})

    return _build_outline_from_entries(
        course_title=course_title,
        entries=entries,
        outline_source="local_candidates",
    )


def _build_local_outline(*, parsed_markdown: str, course_title: str) -> Dict[str, Any]:
    for builder in (
        _extract_local_outline_from_toc,
        _extract_local_outline_from_headings,
        _extract_local_outline_from_candidates,
    ):
        outline = builder(markdown_text=parsed_markdown, course_title=course_title)
        if outline and outline.get("chapters"):
            return outline

    raise TextbookKnowledgeGraphError("Failed to reconstruct textbook directory from parsed textbook.")


def _looks_like_toc_entry(line: str) -> bool:
    title = _clean_outline_title(line)
    if not title:
        return False

    normalized = _normalize_whitespace(str(line or ""))
    has_page_number = bool(re.search(r"\d{1,4}\s*$", normalized))
    has_leader = bool(re.search(r"[.…·]{2,}", normalized))
    role = _outline_role_from_title(title)
    if role in {"chapter", "section"} and (has_page_number or has_leader):
        return True

    if has_page_number:
        text_without_digits = re.sub(r"[\d\s._\-·…]+$", "", normalized)
        return len(re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text_without_digits)) >= 2
    return False


def _find_toc_body_start(lines: List[str]) -> int:
    toc_start: Optional[int] = None
    scan_limit = min(len(lines), 500)

    for line_index, line in enumerate(lines[:scan_limit]):
        if _normalize_for_compare(_clean_outline_title(line)) in {"目录", "contents", "tableofcontents"}:
            toc_start = line_index
            break

    if toc_start is None:
        return 0

    last_entry_index = toc_start
    found_entry = False
    noise_run = 0
    search_limit = min(len(lines), toc_start + 1200)

    for line_index in range(toc_start + 1, search_limit):
        raw_line = lines[line_index]
        if _looks_like_toc_entry(raw_line):
            found_entry = True
            noise_run = 0
            last_entry_index = line_index
            continue

        if not str(raw_line or "").strip():
            continue

        if found_entry:
            noise_run += 1
            if noise_run >= 8:
                break

    body_start = min(last_entry_index + 1, len(lines))
    while body_start < len(lines) and not str(lines[body_start] or "").strip():
        body_start += 1
    return body_start


def _line_matches_outline_title(line: str, title: str) -> bool:
    stripped_line = _normalize_whitespace(line)
    normalized_line = _normalize_for_compare(stripped_line)
    normalized_title = _normalize_for_compare(title)
    if not normalized_line or not normalized_title:
        return False
    if normalized_line == normalized_title:
        return True
    if len(normalized_title) >= 6 and normalized_title in normalized_line:
        return True

    title_prefix = _extract_numeric_prefix(title)
    line_prefix = _extract_numeric_prefix(stripped_line)
    if title_prefix and line_prefix and title_prefix == line_prefix:
        title_body = _normalize_for_compare(_strip_title_prefix(title))
        line_body = _normalize_for_compare(_strip_title_prefix(stripped_line))
        if not title_body or not line_body:
            return True
        if title_body in line_body or line_body in title_body:
            return True
    return False


def _find_outline_anchor(
    *,
    lines: List[str],
    title: str,
    start_index: int,
    end_index: Optional[int] = None,
    prefer_after_index: Optional[int] = None,
) -> Optional[int]:
    limit = len(lines) if end_index is None else min(end_index, len(lines))
    matches: List[int] = []
    for line_index in range(max(start_index, 0), limit):
        if _line_matches_outline_title(lines[line_index], title):
            matches.append(line_index)

    if not matches:
        return None

    if prefer_after_index is not None:
        preferred_matches = [item for item in matches if item >= prefer_after_index]
        if preferred_matches:
            return preferred_matches[0]

    toc_threshold = max(40, int(len(lines) * 0.2))
    if len(matches) > 1 and matches[0] <= toc_threshold:
        later_matches = [item for item in matches[1:] if item > toc_threshold]
        if later_matches:
            return later_matches[0]
    return matches[0]


def _split_parsed_markdown_by_outline(
    *,
    parsed_markdown: str,
    outline: Dict[str, Any],
) -> List[Dict[str, Any]]:
    lines = parsed_markdown.splitlines()
    body_start_index = _find_toc_body_start(lines)
    outline_chapters = outline.get("chapters") if isinstance(outline.get("chapters"), list) else []
    if not outline_chapters:
        raise TextbookKnowledgeGraphError("Cannot split textbook without outline chapters.")

    chapter_starts: List[int] = []
    search_floor = body_start_index
    for chapter in outline_chapters:
        chapter_title = str(chapter.get("title") or "").strip()
        section_titles = [
            str(section.get("title") or "").strip()
            for section in chapter.get("sections") if isinstance(chapter.get("sections"), list)
            for section in [section]
            if isinstance(section, dict) and str(section.get("title") or "").strip()
        ]
        chapter_anchor = _find_outline_anchor(
            lines=lines,
            title=chapter_title,
            start_index=search_floor,
            prefer_after_index=body_start_index,
        )
        section_anchors = [
            anchor
            for anchor in (
                _find_outline_anchor(
                    lines=lines,
                    title=section_title,
                    start_index=max(search_floor, body_start_index),
                )
                for section_title in section_titles
            )
            if anchor is not None
        ]

        start_index = chapter_anchor
        if start_index is None and section_anchors:
            start_index = min(section_anchors)
            if search_floor == body_start_index and body_start_index < start_index:
                start_index = body_start_index
        if start_index is None:
            start_index = search_floor

        if chapter_starts:
            start_index = max(start_index, chapter_starts[-1] + 1)
        chapter_starts.append(start_index)
        search_floor = min(start_index + 1, len(lines))

    split_chapters: List[Dict[str, Any]] = []
    for chapter_index, chapter in enumerate(outline_chapters):
        chapter_start = chapter_starts[chapter_index]
        chapter_end = chapter_starts[chapter_index + 1] if chapter_index + 1 < len(chapter_starts) else len(lines)
        if chapter_end < chapter_start:
            chapter_end = chapter_start

        section_defs = chapter.get("sections") if isinstance(chapter.get("sections"), list) else []
        section_starts: List[tuple[Dict[str, Any], int]] = []
        section_floor = chapter_start
        for section in section_defs:
            if not isinstance(section, dict):
                continue
            section_title = str(section.get("title") or "").strip()
            if not section_title:
                continue
            anchor = _find_outline_anchor(
                lines=lines,
                title=section_title,
                start_index=section_floor,
                end_index=chapter_end,
            )
            if anchor is None:
                continue
            if section_starts and anchor <= section_starts[-1][1]:
                continue
            section_starts.append((section, anchor))
            section_floor = min(anchor + 1, chapter_end)

        chapter_content = "\n".join(lines[chapter_start:chapter_end]).strip()
        sections: List[Dict[str, Any]] = []
        if section_starts:
            for section_index, (section, section_start) in enumerate(section_starts):
                section_end = (
                    section_starts[section_index + 1][1]
                    if section_index + 1 < len(section_starts)
                    else chapter_end
                )
                sections.append(
                    {
                        "title": str(section.get("title") or ""),
                        "content": "\n".join(lines[section_start:section_end]).strip(),
                    }
                )
        else:
            sections.append(
                {
                    "title": str(chapter.get("title") or ""),
                    "content": chapter_content,
                }
            )

        split_chapters.append(
            {
                "title": str(chapter.get("title") or f"Chapter {chapter_index + 1}"),
                "content": chapter_content,
                "sections": sections,
            }
        )

    return split_chapters


def _merge_outline_with_splits(
    *,
    course_title: str,
    split_chapters: List[Dict[str, Any]],
    outline: Dict[str, Any],
) -> Dict[str, Any]:
    llm_chapters = outline.get("chapters")
    if not isinstance(llm_chapters, list):
        llm_chapters = []

    merged_chapters: List[Dict[str, Any]] = []
    for chapter_index, split_chapter in enumerate(split_chapters):
        llm_chapter = llm_chapters[chapter_index] if chapter_index < len(llm_chapters) else {}
        chapter_title = _normalize_whitespace(str(llm_chapter.get("title") or split_chapter["title"]))
        section_drafts = split_chapter.get("sections") if isinstance(split_chapter.get("sections"), list) else []
        llm_sections = llm_chapter.get("sections") if isinstance(llm_chapter.get("sections"), list) else []

        merged_sections: List[Dict[str, Any]] = []
        for section_index, section_draft in enumerate(section_drafts):
            llm_section = llm_sections[section_index] if section_index < len(llm_sections) else {}
            section_title = _normalize_whitespace(str(llm_section.get("title") or section_draft["title"]))
            section_content = str(section_draft.get("content") or "").strip()
            merged_sections.append(
                {
                    "title": section_title or section_draft["title"],
                    "summary": _normalize_whitespace(
                        str(llm_section.get("summary") or _summarize_text(section_content, max_chars=120))
                    ),
                    "concepts": _normalize_concepts(llm_section.get("concepts")),
                    "content": section_content,
                }
            )

        merged_chapters.append(
            {
                "title": chapter_title or split_chapter["title"],
                "summary": _normalize_whitespace(
                    str(llm_chapter.get("summary") or _summarize_text(split_chapter["content"], max_chars=160))
                ),
                "content": str(split_chapter["content"] or "").strip(),
                "sections": merged_sections,
            }
        )

    return {
        "course_title": _normalize_whitespace(str(outline.get("course_title") or course_title)) or course_title,
        "summary": _normalize_whitespace(
            str(outline.get("summary") or f"{course_title} textbook knowledge graph")
        ),
        "chapters": merged_chapters,
        "outline_source": str(outline.get("_provider") or "llm"),
        "env_path": str(outline.get("_env_path") or ""),
    }


def _build_course_summary(course_title: str, chapters: List[Dict[str, Any]]) -> str:
    parts = [
        f"{chapter.get('title')}: {chapter.get('summary')}"
        for chapter in chapters
        if str(chapter.get("title") or "").strip() and str(chapter.get("summary") or "").strip()
    ]
    if not parts:
        return f"{course_title} textbook knowledge graph"
    return _summarize_text(" ".join(parts), max_chars=240)


def _prepare_chapter_markdown_for_llm(chapter_content: str) -> str:
    content = str(chapter_content or "").strip()
    max_chars = int(os.getenv("TEXTBOOK_LLM_CHAPTER_MAX_CHARS", "50000"))
    if max_chars <= 0 or len(content) <= max_chars:
        return content

    head_chars = max_chars // 2
    tail_chars = max_chars - head_chars
    return (
        content[:head_chars].rstrip()
        + "\n\n[... middle content omitted for length ...]\n\n"
        + content[-tail_chars:].lstrip()
    )


def _invoke_chapter_outline_model(
    *,
    course_title: str,
    split_chapter: Dict[str, Any],
    config: Dict[str, str],
) -> Dict[str, Any]:
    local_section_candidates = [
        str(section.get("title") or "").strip()
        for section in split_chapter.get("sections")
        if isinstance(split_chapter.get("sections"), list)
        for section in [section]
        if isinstance(section, dict) and str(section.get("title") or "").strip()
    ]
    payload = {
        "course_title": course_title,
        "chapter_title": str(split_chapter.get("title") or "").strip(),
        "chapter_markdown": _prepare_chapter_markdown_for_llm(str(split_chapter.get("content") or "")),
        "section_candidates": local_section_candidates,
    }

    system_prompt = (
        "You process one textbook chapter that has already been split locally from a trusted table of contents. "
        "Keep the provided chapter title fixed. Decide whether this chapter should stay unsplit or be split into one level of sections only. "
        "Return JSON only."
    )
    user_prompt = (
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "title": "string",\n'
        '  "summary": "string",\n'
        '  "split_strategy": "none" | "one_level",\n'
        '  "sections": [\n'
        "    {\n"
        '      "title": "string",\n'
        '      "summary": "string",\n'
        '      "concepts": ["string"]\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Keep the provided chapter title unchanged.\n"
        "- Split by section at one level only, or do not split this chapter.\n"
        "- Do not create nested subsections.\n"
        "- Prefer titles from section_candidates when they match the content.\n"
        "- You may return no sections if the content should remain one whole chapter block.\n"
        "- Ground every summary and concept in the provided excerpt.\n"
        "- Each section should contain 2 to 6 concise concepts.\n"
        "- No markdown fences, no explanation, JSON only.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    response = requests.post(
        f"{config['api_base']}/chat/completions",
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=180,
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise TextbookKnowledgeGraphError("LLM response did not contain choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(
            str(item.get("text") or "").strip()
            for item in content
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )

    return _extract_json_object(str(content or ""))


def _split_content_by_section_titles(
    *,
    chapter_content: str,
    section_titles: List[str],
) -> List[Dict[str, str]]:
    if not section_titles:
        return []

    lines = str(chapter_content or "").splitlines()
    section_starts: List[tuple[str, int]] = []
    floor = 0
    for section_title in section_titles:
        anchor = _find_outline_anchor(lines=lines, title=section_title, start_index=floor)
        if anchor is None:
            continue
        if section_starts and anchor <= section_starts[-1][1]:
            continue
        section_starts.append((section_title, anchor))
        floor = min(anchor + 1, len(lines))

    if not section_starts:
        return []

    sections: List[Dict[str, str]] = []
    for section_index, (section_title, section_start) in enumerate(section_starts):
        section_end = section_starts[section_index + 1][1] if section_index + 1 < len(section_starts) else len(lines)
        sections.append(
            {
                "title": section_title,
                "content": "\n".join(lines[section_start:section_end]).strip(),
            }
        )
    return sections


def _pick_matching_llm_section(
    *,
    llm_sections: List[Any],
    section_title: str,
    section_index: int,
) -> Dict[str, Any]:
    if section_index < len(llm_sections) and isinstance(llm_sections[section_index], dict):
        return llm_sections[section_index]

    normalized_title = _normalize_for_compare(section_title)
    for item in llm_sections:
        if not isinstance(item, dict):
            continue
        if _normalize_for_compare(str(item.get("title") or "")) == normalized_title:
            return item

    return {}


def _merge_split_chapter_with_llm(
    *,
    split_chapter: Dict[str, Any],
    llm_chapter: Optional[Dict[str, Any]] = None,
    fallback_to_local_sections: bool = False,
) -> Dict[str, Any]:
    llm_chapter = llm_chapter if isinstance(llm_chapter, dict) else {}
    llm_sections = llm_chapter.get("sections") if isinstance(llm_chapter.get("sections"), list) else []
    split_sections = split_chapter.get("sections") if isinstance(split_chapter.get("sections"), list) else []
    split_strategy = str(llm_chapter.get("split_strategy") or "").strip().lower()

    if llm_sections:
        requested_titles = [
            str(section.get("title") or "").strip()
            for section in llm_sections
            if isinstance(section, dict) and str(section.get("title") or "").strip()
        ]
        section_drafts = _split_content_by_section_titles(
            chapter_content=str(split_chapter.get("content") or ""),
            section_titles=requested_titles,
        )
        if not section_drafts and fallback_to_local_sections:
            section_drafts = [
                {
                    "title": str(section.get("title") or "").strip(),
                    "content": str(section.get("content") or "").strip(),
                }
                for section in split_sections
                if isinstance(section, dict) and str(section.get("title") or "").strip()
            ]
    elif fallback_to_local_sections and split_strategy != "none":
        section_drafts = [
            {
                "title": str(section.get("title") or "").strip(),
                "content": str(section.get("content") or "").strip(),
            }
            for section in split_sections
            if isinstance(section, dict) and str(section.get("title") or "").strip()
        ]
    else:
        section_drafts = []

    merged_sections: List[Dict[str, Any]] = []
    for section_index, section_draft in enumerate(section_drafts):
        if not isinstance(section_draft, dict):
            continue
        section_title = str(section_draft.get("title") or "").strip()
        section_content = str(section_draft.get("content") or "").strip()
        llm_section = _pick_matching_llm_section(
            llm_sections=llm_sections,
            section_title=section_title,
            section_index=section_index,
        )
        merged_sections.append(
            {
                "title": section_title,
                "summary": _normalize_whitespace(
                    str(llm_section.get("summary") or _summarize_text(section_content, max_chars=120))
                ),
                "concepts": _normalize_concepts(llm_section.get("concepts")),
                "content": section_content,
            }
        )

    chapter_title = str(split_chapter.get("title") or "").strip()
    chapter_content = str(split_chapter.get("content") or "").strip()
    return {
        "title": chapter_title,
        "summary": _normalize_whitespace(
            str(llm_chapter.get("summary") or _summarize_text(chapter_content, max_chars=160))
        ),
        "content": chapter_content,
        "sections": merged_sections,
    }


def _enrich_split_chapters_with_llm(
    *,
    course_title: str,
    split_chapters: List[Dict[str, Any]],
    outline_source: str,
    explicit_env_path: Optional[str] = None,
) -> Dict[str, Any]:
    warnings: List[str] = []

    try:
        config = _resolve_openai_compatible_config(explicit_env_path)
    except TextbookKnowledgeGraphError as exc:
        warnings.append(str(exc))
        merged_chapters = [
            _merge_split_chapter_with_llm(
                split_chapter=split_chapter,
                fallback_to_local_sections=True,
            )
            for split_chapter in split_chapters
        ]
        return {
            "course_title": course_title,
            "summary": _build_course_summary(course_title, merged_chapters),
            "chapters": merged_chapters,
            "outline_source": outline_source,
            "env_path": "",
            "warnings": warnings,
        }

    merged_chapters: List[Dict[str, Any]] = []
    for split_chapter in split_chapters:
        chapter_title = str(split_chapter.get("title") or "").strip() or "Untitled Chapter"
        try:
            llm_chapter = _invoke_chapter_outline_model(
                course_title=course_title,
                split_chapter=split_chapter,
                config=config,
            )
        except (TextbookKnowledgeGraphError, requests.RequestException) as exc:
            warnings.append(f"LLM enrichment failed for {chapter_title}: {exc}")
            llm_chapter = {}

        merged_chapters.append(
            _merge_split_chapter_with_llm(
                split_chapter=split_chapter,
                llm_chapter=llm_chapter,
                fallback_to_local_sections=not bool(llm_chapter),
            )
        )

    return {
        "course_title": course_title,
        "summary": _build_course_summary(course_title, merged_chapters),
        "chapters": merged_chapters,
        "outline_source": f"{outline_source}+{config['provider']}",
        "env_path": str(config["env_path"]),
        "warnings": warnings,
    }


def _build_llm_payload(
    *,
    course_title: str,
    parsed_markdown: str,
    outline_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "course_title": course_title,
        "first_20_pages_window": _extract_first_page_window(parsed_markdown, page_limit=20),
        "parsed_markdown": parsed_markdown,
        "outline_candidates": [
            {
                "title": candidate["title"],
                "role": candidate["role"],
                "level": candidate["level"],
                "line_index": candidate["line_index"],
            }
            for candidate in outline_candidates
        ],
    }


def _build_knowledge_graph(course_title: str, summary: str, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
    chapter_nodes: List[Dict[str, Any]] = []
    for chapter_index, chapter in enumerate(chapters, start=1):
        section_nodes: List[Dict[str, Any]] = []
        for section_index, section in enumerate(chapter.get("sections") or [], start=1):
            concept_nodes = [
                {
                    "id": f"chapter-{chapter_index}-section-{section_index}-concept-{concept_index}",
                    "label": concept,
                    "children": [],
                    "data": {
                        "level": 3,
                        "summary": concept,
                        "hasChildren": False,
                        "type": "concept",
                    },
                }
                for concept_index, concept in enumerate(section.get("concepts") or [], start=1)
            ]
            section_nodes.append(
                {
                    "id": f"chapter-{chapter_index}-section-{section_index}",
                    "label": str(section.get("title") or f"Section {section_index}"),
                    "children": concept_nodes,
                    "data": {
                        "level": 2,
                        "summary": str(section.get("summary") or ""),
                        "hasChildren": bool(concept_nodes),
                        "type": "section",
                    },
                }
            )

        chapter_nodes.append(
            {
                "id": f"chapter-{chapter_index}",
                "label": str(chapter.get("title") or f"Chapter {chapter_index}"),
                "children": section_nodes,
                "data": {
                    "level": 1,
                    "summary": str(chapter.get("summary") or ""),
                    "hasChildren": bool(section_nodes),
                    "type": "chapter",
                },
            }
        )

    return {
        "id": "root",
        "label": course_title,
        "children": chapter_nodes,
        "data": {
            "level": 0,
            "summary": summary,
            "hasChildren": bool(chapter_nodes),
            "type": "course",
        },
    }


def _latest_source_document(manager: CourseStorageManager, course_id: str, filename: str) -> Dict[str, Any]:
    for item in reversed(manager.get_knowledge_base_index(course_id)):
        if str(item.get("filename") or "") == filename:
            return item
    raise TextbookKnowledgeGraphError(f"Uploaded source document not found in course index: {filename}")


def _cleanup_existing_split_files(*, split_dir: Path, rag_system: Any) -> None:
    if not split_dir.exists():
        return

    for old_file in split_dir.glob("*.md"):
        try:
            rag_system.delete_document(str(old_file))
        except Exception:
            pass

    shutil.rmtree(split_dir, ignore_errors=True)


def _write_split_documents(
    *,
    split_dir: Path,
    chapters: List[Dict[str, Any]],
    course_dir: Path,
) -> List[Dict[str, Any]]:
    split_dir.mkdir(parents=True, exist_ok=True)
    split_documents: List[Dict[str, Any]] = []
    for chapter_index, chapter in enumerate(chapters, start=1):
        title = str(chapter.get("title") or f"Chapter {chapter_index}")
        safe_name = _normalize_slug(title, f"chapter-{chapter_index}")
        filename = f"{chapter_index:02d}-{safe_name}.md"
        file_path = split_dir / filename
        content = str(chapter.get("content") or "").strip()
        if not content.startswith("#"):
            content = f"# {title}\n\n{content}"
        file_path.write_text(content, encoding="utf-8")
        split_documents.append(
            {
                "id": f"split-{chapter_index}",
                "title": title,
                "section_titles": [str(section.get("title") or "") for section in chapter.get("sections") or []],
                "file_path": str(file_path.relative_to(course_dir)).replace("\\", "/"),
                "absolute_path": str(file_path),
                "char_count": len(content),
                "preview": _summarize_text(content, max_chars=220),
            }
        )
    return split_documents


def _vectorize_split_documents(split_documents: List[Dict[str, Any]], rag_system: Any) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for split_document in split_documents:
        absolute_path = str(split_document["absolute_path"])
        import_result = rag_system.import_document(absolute_path, force_reimport=False)
        results.append(
            {
                "title": split_document["title"],
                "file_path": split_document["file_path"],
                "status": str(import_result.get("status") or "unknown"),
                "message": str(import_result.get("message") or ""),
                "chunk_count": int(import_result.get("chunk_count") or 0),
            }
        )
    return results


def _parse_textbook_content(file_path: Path, rag_system: Any) -> tuple[str, str, List[str]]:
    suffix = file_path.suffix.lower()
    warnings: List[str] = []

    if suffix in {".md", ".markdown"}:
        return _ensure_markdown_title(_read_text_file(file_path), file_path.stem), "markdown", warnings

    if suffix == ".txt":
        return _ensure_markdown_title(_read_text_file(file_path), file_path.stem), "text", warnings

    if suffix in {".doc", ".docx"}:
        parsed = _normalize_whitespace(docx2txt.process(str(file_path)))
        if not parsed:
            raise TextbookKnowledgeGraphError(f"No readable text extracted from Word document: {file_path.name}")
        return _ensure_markdown_title(parsed, file_path.stem), "docx2txt", warnings

    if suffix != ".pdf":
        raise TextbookKnowledgeGraphError(f"Unsupported textbook format: {file_path.suffix}")

    processor = getattr(rag_system, "document_processor", None)
    if not (processor and hasattr(processor, "_parse_pdf_with_mineru")):
        raise TextbookKnowledgeGraphError(
            "MinerU parser is required for PDF textbooks, but it is unavailable in the current RAG runtime."
        )

    try:
        mineru_result = processor._parse_pdf_with_mineru(
            str(file_path),
            pages_per_chunk=int(os.getenv("RAG_MINERU_PAGES_PER_CHUNK", "20")),
            max_workers=int(os.getenv("RAG_MINERU_MAX_WORKERS", "1")),
        )
    except Exception as exc:  # pragma: no cover - depends on runtime install
        raise TextbookKnowledgeGraphError(f"MinerU parsing failed for PDF {file_path.name}: {exc}") from exc

    markdown_text = str(mineru_result.get("markdown_text") or "").strip()
    if mineru_result.get("success") and markdown_text:
        return markdown_text, "mineru", warnings

    error_detail = str(mineru_result.get("error") or "unknown_mineru_error").strip()
    if not markdown_text:
        error_detail = f"{error_detail}; no markdown output"
    raise TextbookKnowledgeGraphError(f"MinerU parsing failed for PDF {file_path.name}: {error_detail}")


def import_textbook_into_knowledge_graph(
    *,
    course_id: str,
    filename: str,
    file_bytes: bytes,
    manager: CourseStorageManager,
    rag_system: Any,
    explicit_env_path: Optional[str] = None,
) -> Dict[str, Any]:
    course_info = manager.get_course_info(course_id)
    if not course_info:
        raise TextbookKnowledgeGraphError(f"Course does not exist: {course_id}")

    relative_path = manager.save_knowledge_base_file(course_id, file_bytes, filename)
    if not relative_path:
        raise TextbookKnowledgeGraphError("Failed to persist uploaded textbook to course storage.")

    source_document = _latest_source_document(manager, course_id, filename)
    course_dir = manager.get_course_dir(course_id)
    file_path = course_dir / relative_path

    parsed_markdown, parser_used, warnings = _parse_textbook_content(file_path, rag_system)
    outline_candidates = _extract_outline_candidates(parsed_markdown)
    if not outline_candidates:
        raise TextbookKnowledgeGraphError("Failed to extract textbook directory candidates from parsed textbook.")

    course_title = str(course_info.get("title") or file_path.stem).strip() or file_path.stem
    llm_payload = _build_llm_payload(
        course_title=course_title,
        parsed_markdown=parsed_markdown,
        outline_candidates=outline_candidates,
    )
    outline = _invoke_outline_model(payload=llm_payload, explicit_env_path=explicit_env_path)
    normalized_outline = _normalize_outline_from_llm(
        course_title=course_title,
        outline=outline,
    )
    split_chapters = _split_parsed_markdown_by_outline(
        parsed_markdown=parsed_markdown,
        outline=normalized_outline,
    )
    merged_outline = _merge_outline_with_splits(
        course_title=course_title,
        split_chapters=split_chapters,
        outline=normalized_outline,
    )

    safe_source_name = _normalize_slug(file_path.stem, "textbook")
    derived_root = course_dir / "knowledge_base" / "derived" / "textbook_graph" / safe_source_name
    split_dir = derived_root / "chapters"
    _cleanup_existing_split_files(split_dir=split_dir, rag_system=rag_system)
    derived_root.mkdir(parents=True, exist_ok=True)

    parsed_markdown_path = derived_root / f"{safe_source_name}.parsed.md"
    parsed_markdown_path.write_text(parsed_markdown, encoding="utf-8")

    split_documents = _write_split_documents(
        split_dir=split_dir,
        chapters=merged_outline["chapters"],
        course_dir=course_dir,
    )
    vectorized_documents = _vectorize_split_documents(split_documents, rag_system)

    knowledge_graph = _build_knowledge_graph(
        merged_outline["course_title"],
        merged_outline["summary"],
        merged_outline["chapters"],
    )
    if not manager.save_knowledge_graph(course_id, knowledge_graph):
        raise TextbookKnowledgeGraphError("Failed to persist generated knowledge graph.")

    material_id = f"textbook-graph-{safe_source_name}"
    stored_payload = {
        "title": f"{merged_outline['course_title']} textbook graph",
        "material_type": "graph",
        "source_document_id": source_document.get("id"),
        "source_filename": filename,
        "parser_used": parser_used,
        "outline_source": merged_outline["outline_source"],
        "llm_env_path": merged_outline["env_path"],
        "warnings": warnings,
        "parsed_markdown_path": str(parsed_markdown_path.relative_to(course_dir)).replace("\\", "/"),
        "split_documents": [
            {
                "id": item["id"],
                "title": item["title"],
                "section_titles": item["section_titles"],
                "file_path": item["file_path"],
                "char_count": item["char_count"],
                "preview": item["preview"],
            }
            for item in split_documents
        ],
        "vectorized_documents": vectorized_documents,
        "knowledge_graph": knowledge_graph,
        "chapters": [
            {
                "title": chapter["title"],
                "summary": chapter["summary"],
                "sections": [
                    {
                        "title": section["title"],
                        "summary": section["summary"],
                        "concepts": section["concepts"],
                    }
                    for section in chapter["sections"]
                ],
            }
            for chapter in merged_outline["chapters"]
        ],
    }
    if not manager.save_generated_material(course_id, "graph", material_id, stored_payload):
        raise TextbookKnowledgeGraphError("Failed to persist generated graph material.")

    return {
        "source_document": {
            "id": str(source_document.get("id") or ""),
            "name": str(source_document.get("filename") or filename),
            "type": "file",
            "file_path": str(source_document.get("path") or relative_path).replace("\\", "/"),
            "course_id": course_id,
            "created_at": str(source_document.get("uploaded_at") or ""),
            "updated_at": str(source_document.get("updated_at") or ""),
        },
        "parser_used": parser_used,
        "outline_source": merged_outline["outline_source"],
        "llm_env_path": merged_outline["env_path"],
        "graph_material_id": material_id,
        "parsed_markdown_path": str(parsed_markdown_path.relative_to(course_dir)).replace("\\", "/"),
        "knowledge_graph": {"root": knowledge_graph},
        "split_documents": [
            {
                "id": item["id"],
                "title": item["title"],
                "section_titles": item["section_titles"],
                "file_path": item["file_path"],
                "char_count": item["char_count"],
                "preview": item["preview"],
            }
            for item in split_documents
        ],
        "vectorized_documents": vectorized_documents,
        "warnings": warnings,
    }
