"""Markdown outline → structured data converters.

Pure functions, no LLM calls, no external imports at module level.
Used by report.py to build chapter lists.
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
