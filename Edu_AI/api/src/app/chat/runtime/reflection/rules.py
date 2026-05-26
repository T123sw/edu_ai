from __future__ import annotations

import re

from app.chat.runtime.reflection.base import BaseReflector, ReflectVerdict


class LengthReflector(BaseReflector):
    """Blocks empty or too-short search results."""

    priority = 0
    _APPLIES_TO = {"rag_search", "web_search"}

    def applies_to(self, tool_name: str) -> bool:
        return tool_name in self._APPLIES_TO

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")

        payload = result.get("payload") or {}
        min_length = step_constraints.get("min_answer_length", 50)

        if tool_name == "rag_search":
            text = str(payload.get("answer", "")).strip()
        else:
            text = str(payload.get("summary", "")).strip()

        if len(text) < min_length:
            return ReflectVerdict(
                verdict="retry",
                hint=(
                    f"{'知识库' if tool_name == 'rag_search' else '联网'}检索内容过少"
                    f"（{len(text)}字 < {min_length}字），"
                    f"{'尝试联网搜索补充' if tool_name == 'rag_search' else '尝试换关键词重试'}"
                ),
                severity="blocking",
            )

        return ReflectVerdict(verdict="pass")


class SourcesReflector(BaseReflector):
    """Warns when required sources are missing from search results."""

    priority = 1
    _APPLIES_TO = {"rag_search", "web_search"}

    def applies_to(self, tool_name: str) -> bool:
        return tool_name in self._APPLIES_TO

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")

        if not step_constraints.get("require_sources", False):
            return ReflectVerdict(verdict="pass")

        payload = result.get("payload") or {}
        sources = payload.get("sources") or payload.get("items") or []
        min_sources = step_constraints.get("min_sources", 1)

        if len(sources) < min_sources:
            return ReflectVerdict(
                verdict="retry",
                hint=f"搜索结果缺少来源引用（需要 ≥{min_sources} 个来源，当前 {len(sources)} 个），重试搜索",
                severity="warning",
            )

        return ReflectVerdict(verdict="pass")


class ChapterCountReflector(BaseReflector):
    """Ensures draft_outline has sufficient chapters and length."""

    priority = 0

    def applies_to(self, tool_name: str) -> bool:
        return tool_name == "draft_outline"

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")

        payload = result.get("payload") or {}
        outline_md = str(payload.get("outline_markdown", "")).strip()

        min_chapters = step_constraints.get("min_chapters", 3)
        chapter_count = len(re.findall(r"^##\s", outline_md, re.MULTILINE))

        if chapter_count < min_chapters:
            return ReflectVerdict(
                verdict="retry",
                hint=(
                    f"大纲章节数量不足（{chapter_count} 章 < 要求 {min_chapters} 章），"
                    "请重新生成更详细的大纲"
                ),
                severity="blocking",
            )

        min_length = step_constraints.get("min_outline_length", 200)
        if len(outline_md) < min_length:
            return ReflectVerdict(
                verdict="retry",
                hint=f"大纲内容过短（{len(outline_md)}字 < {min_length}字），请生成更详细的大纲",
                severity="blocking",
            )

        return ReflectVerdict(verdict="pass")


# ─── Pipeline ─────────────────────────────────────────────────────────────────

_VERDICT_PRIORITY = {"abort": 4, "replan": 3, "retry": 2, "pass_with_warning": 1, "pass": 0}


class ReflectorPipeline:
    def __init__(self, reflectors: list[BaseReflector]):
        self._reflectors = sorted(reflectors, key=lambda r: r.priority)

    @classmethod
    def default(cls) -> "ReflectorPipeline":
        return cls([LengthReflector(), SourcesReflector(), ChapterCountReflector()])

    def evaluate_all(
        self,
        tool_name: str,
        result: dict,
        state: dict,
        step_constraints: dict,
    ) -> list[ReflectVerdict]:
        applicable = [r for r in self._reflectors if r.applies_to(tool_name)]
        if not applicable:
            return [ReflectVerdict(verdict="pass")]

        verdicts: list[ReflectVerdict] = []
        for reflector in applicable:
            v = reflector.evaluate(tool_name, result, state, step_constraints)
            verdicts.append(v)
            # Stop early on first blocking issue
            if v.severity == "blocking" and v.verdict in ("retry", "replan", "abort"):
                break

        return verdicts
