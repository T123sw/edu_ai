from __future__ import annotations

import re

from app.chat.domain.generation_context import GenerationContext


class GenerationContextBuilder:
    @staticmethod
    def _clean_phrase(value) -> str:
        return str(value or "").strip()

    def _collect_relevance_phrases(self, *, request, memory: dict) -> list[str]:
        phrases: list[str] = []
        for key in ("current_topics", "user_goals", "confirmed_facts", "teaching_issues", "student_signals"):
            phrases.extend(list(memory.get(key) or []))
        phrases.append(getattr(request, "question", "") or "")

        normalized: list[str] = []
        seen: set[str] = set()
        for item in phrases:
            phrase = self._clean_phrase(item)
            if not phrase or len(phrase) < 2:
                continue
            if phrase in seen:
                continue
            seen.add(phrase)
            normalized.append(phrase)
        return normalized

    @staticmethod
    def _overlap_score(content: str, phrase: str) -> int:
        if not content or not phrase:
            return 0
        if phrase in content:
            return min(len(phrase), 8) + 4

        score = 0
        parts = [part for part in re.split(r"[，。！？；、\s]", phrase) if len(part) >= 2]
        for part in parts:
            if part in content:
                score += min(len(part), 4)
        return score

    def _score_message(self, *, message: dict, phrases: list[str]) -> int:
        content = str((message or {}).get("content") or "").strip()
        if not content:
            return 0
        score = 0
        for phrase in phrases:
            score += self._overlap_score(content, phrase)
        return score

    def _select_relevant_messages(self, *, request, snapshot, memory: dict, limit: int = 6) -> list[dict]:
        messages = list(getattr(snapshot, "recent_messages", []) or [])
        if not messages:
            return []

        phrases = self._collect_relevance_phrases(request=request, memory=memory)
        scored: list[tuple[int, int, dict]] = []
        for index, message in enumerate(messages):
            score = self._score_message(message=message, phrases=phrases)
            if score > 0:
                scored.append((score, index, message))

        if not scored:
            return messages[-limit:]

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = sorted(scored[:limit], key=lambda item: item[1])
        return [item[2] for item in selected]

    def build_for_resource(self, *, request, snapshot, resource_type: str) -> GenerationContext:
        memory = dict(getattr(snapshot, "conversation_memory", {}) or {})
        active_context = dict(getattr(snapshot, "active_context", {}) or {})
        selected_doc_ids = list(
            active_context.get("pinned_doc_ids")
            or getattr(getattr(request, "capability", None), "selected_doc_ids", [])
            or []
        )
        recent_relevant_messages = self._select_relevant_messages(
            request=request,
            snapshot=snapshot,
            memory=memory,
            limit=6,
        )
        referenced_artifact_ids = list(getattr(snapshot, "referenced_artifact_ids", []) or [])

        return GenerationContext(
            conversation_id=(
                getattr(snapshot, "conversation_id", "")
                or getattr(request, "conversation_id", "")
                or ""
            ),
            resource_type=resource_type,
            summary_text=getattr(snapshot, "summary", "") or "",
            current_topics=list(memory.get("current_topics") or []),
            user_goals=list(memory.get("user_goals") or []),
            confirmed_facts=list(memory.get("confirmed_facts") or []),
            constraints=dict(memory.get("constraints") or {}),
            teaching_issues=list(memory.get("teaching_issues") or []),
            student_signals=list(memory.get("student_signals") or []),
            evidence_points=list(memory.get("evidence_points") or []),
            selected_doc_ids=selected_doc_ids,
            referenced_artifact_ids=referenced_artifact_ids,
            current_course_id=active_context.get("current_course_id"),
            active_artifact_id=active_context.get("active_artifact_id"),
            active_artifact_type=active_context.get("active_artifact_type"),
            recent_relevant_messages=recent_relevant_messages,
            source_scope={
                "from_summary": bool(getattr(snapshot, "summary", "")),
                "from_memory": bool(memory),
                "from_recent_messages": bool(recent_relevant_messages),
                "from_docs": bool(selected_doc_ids),
                "from_artifacts": bool(referenced_artifact_ids),
            },
        )
