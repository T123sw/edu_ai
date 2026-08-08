from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .models import OutlineSection, VisualBrief, VisualSlot


_MAX_SLOTS = {
    "report": 4,
    "blog": 4,
    "lesson_plan": 3,
    "classroom": 5,
    "quiz": 2,
    "flashcard": 3,
    "graph": 2,
    "game": 2,
}
_KINDS = {"diagram", "chart", "photo", "illustration", "any"}
_SOURCES = {"knowledge_base", "web"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _payload(value: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    text = _clean(value)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("visual brief is not valid JSON")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("visual brief is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("visual brief root must be an object")
    return parsed


def _safe_id(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
    return normalized or fallback


def parse_visual_brief(
    value: str | Mapping[str, Any],
    *,
    resource_type: str,
    topic: str,
) -> VisualBrief:
    data = _payload(value)
    sections: list[OutlineSection] = []
    section_ids: set[str] = set()
    for index, raw in enumerate(list(data.get("outline") or []), start=1):
        if not isinstance(raw, Mapping):
            continue
        title = _clean(raw.get("title"))
        if not title:
            continue
        section_id = _safe_id(
            _clean(raw.get("section_id")),
            f"section-{index}",
        )
        if section_id in section_ids:
            continue
        section_ids.add(section_id)
        sections.append(OutlineSection(section_id=section_id, title=title))

    limit = _MAX_SLOTS.get(_clean(resource_type), 2)
    slots: list[VisualSlot] = []
    slot_ids: set[str] = set()
    for index, raw in enumerate(list(data.get("visuals") or []), start=1):
        if len(slots) >= limit or not isinstance(raw, Mapping):
            break
        purpose = _clean(raw.get("purpose"))
        query = _clean(raw.get("query"))
        if not purpose or not query:
            continue
        section_id = _safe_id(
            _clean(raw.get("section_id")),
            sections[0].section_id if sections else "section-1",
        )
        explicit_slot_id = _clean(raw.get("slot_id"))
        slot_id = _safe_id(
            explicit_slot_id,
            f"{section_id}-visual-{len(slots) + 1}",
        )
        if slot_id in slot_ids:
            if explicit_slot_id:
                raise ValueError(f"duplicate visual slot: {slot_id}")
            continue
        slot_ids.add(slot_id)
        kind = _clean(raw.get("preferred_kind"))
        if kind not in _KINDS:
            kind = "any"
        preferences = tuple(
            source
            for source in list(raw.get("source_preference") or [])
            if source in _SOURCES
        ) or ("knowledge_base", "web")
        slots.append(
            VisualSlot(
                slot_id=slot_id,
                section_id=section_id,
                purpose=purpose,
                query=query,
                preferred_kind=kind,
                required=bool(raw.get("required", False)),
                caption_hint=_clean(raw.get("caption_hint")),
                source_preference=preferences,
            )
        )

    return VisualBrief(
        resource_type=_clean(resource_type),
        topic=_clean(topic),
        outline=tuple(sections),
        slots=tuple(slots),
    )
