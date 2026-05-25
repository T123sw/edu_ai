"""Markdown outline → structured data converters.

Pure functions, no LLM calls, no external imports at module level.
Used by report.py (chapter list) and ppt.py (slide list).
"""
from __future__ import annotations


def parse_report_outline(markdown: str) -> list[dict] | None:
    """Markdown → [{title, sections:[{title}]}] for build_report_markdown(outline=).

    Supports two heading levels:
      # Chapter title      → chapter
      ## Section title     → section under current chapter

    Returns None on failure so callers can pass outline=None (engine generates its own).
    """
    try:
        lines = markdown.strip().splitlines()
        chapters: list[dict] = []
        current: dict | None = None
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if s.startswith("# ") and not s.startswith("## "):
                if current:
                    chapters.append(current)
                current = {"title": s[2:].strip(), "sections": []}
            elif s.startswith("## "):
                if current is None:
                    current = {"title": "", "sections": []}
                current["sections"].append({"title": s[3:].strip()})
        if current:
            chapters.append(current)
        return chapters if chapters else None
    except Exception:
        return None


def parse_ppt_slides(markdown: str) -> list[dict] | None:
    """Markdown → [{title, bullets:[str]}] raw dicts for ppt.py to build PptOutlineSlide.

    Supports:
      # or ## heading    → slide title
      - / * bullet       → key point
    """
    try:
        lines = markdown.strip().splitlines()
        slides: list[dict] = []
        current_title = ""
        current_bullets: list[str] = []

        for line in lines:
            s = line.strip()
            if not s:
                continue
            if s.startswith("# ") or s.startswith("## "):
                if current_title:
                    slides.append({"title": current_title, "bullets": current_bullets})
                current_title = s.lstrip("#").strip()
                current_bullets = []
            elif s.startswith("- ") or s.startswith("* "):
                current_bullets.append(s.lstrip("-* ").strip())

        if current_title:
            slides.append({"title": current_title, "bullets": current_bullets})

        return slides if slides else None
    except Exception:
        return None
