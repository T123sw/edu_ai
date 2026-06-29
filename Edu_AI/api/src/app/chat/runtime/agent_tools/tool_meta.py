"""Tool metadata — used by planner/executor for parallel scheduling & strict-mode validation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolMeta:
    name: str
    parallel_safe: bool = False
    mutates_state: bool = False
    depends_on: frozenset[str] = field(default_factory=frozenset)


_TOOL_META: dict[str, ToolMeta] = {
    "rag_search": ToolMeta(
        name="rag_search",
        parallel_safe=True,
        mutates_state=False,
    ),
    "web_search": ToolMeta(
        name="web_search",
        parallel_safe=True,
        mutates_state=False,
    ),
    "image_search": ToolMeta(
        name="image_search",
        parallel_safe=True,
        mutates_state=False,
    ),
    "draft_outline": ToolMeta(
        name="draft_outline",
        parallel_safe=False,
        mutates_state=True,
    ),
    "generate_report": ToolMeta(
        name="generate_report",
        parallel_safe=False,
        mutates_state=True,
        depends_on=frozenset({"draft_outline"}),
    ),
    "generate_ppt": ToolMeta(
        name="generate_ppt",
        parallel_safe=False,
        mutates_state=True,
        depends_on=frozenset({"draft_outline"}),
    ),
    "generate_lesson_plan": ToolMeta(
        name="generate_lesson_plan",
        parallel_safe=False,
        mutates_state=True,
        depends_on=frozenset({"draft_outline"}),
    ),
    "generate_quiz": ToolMeta(
        name="generate_quiz",
        parallel_safe=False,
        mutates_state=True,
    ),
}


# Tools whose results MUST NOT be cached across calls within one conversation turn.
# Image search results vary per call (provider ranking, freshness), and the HITL
# "refresh visuals" flow needs to be able to re-fetch with the same args.
NEVER_CACHE: frozenset[str] = frozenset({"image_search"})


def get_tool_meta(name: str) -> ToolMeta:
    return _TOOL_META.get(name, ToolMeta(name=name))


def is_parallel_safe(names: list[str]) -> bool:
    """All tools in the list are parallel-safe (read-only + no mutual deps)."""
    if len(names) < 2:
        return True
    metas = [get_tool_meta(n) for n in names]
    if not all(m.parallel_safe for m in metas):
        return False
    name_set = set(names)
    return not any(m.depends_on & name_set for m in metas)
