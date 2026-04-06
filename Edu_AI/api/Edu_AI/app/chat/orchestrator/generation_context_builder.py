from __future__ import annotations

import re

from app.chat.domain.generation_context import GenerationContext


class GenerationContextBuilder:
    _SIGNAL_WEIGHTS = {
        "current_topics": 4,
        "user_goals": 3,
        "confirmed_facts": 5,
        "teaching_issues": 5,
        "student_signals": 5,
        "user_stated_facts": 5,
        "user_claims": 5,
        "external_evidence": 4,
        "assistant_hypotheses": 2,
        "constraints": 2,
        "question": 4,
        "summary": 2,
    }

    @staticmethod
    def _is_semantic_message(message: dict) -> bool:
        kind = str((message or {}).get("message_kind") or "").strip()
        return kind not in {"workflow_control", "assistant_meta"}

    @staticmethod
    def _is_active_record(item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        return str(item.get("status") or "").strip().lower() != "retracted"

    @staticmethod
    def _project_confirmed_facts(memory: dict) -> list[str]:
        projected_user_claims: list[str] = []
        for item in list((memory or {}).get("user_claims") or []):
            if not GenerationContextBuilder._is_active_record(item):
                continue
            content = str((item or {}).get("content") or "").strip()
            if content:
                projected_user_claims.append(content)
        if projected_user_claims:
            seen: set[str] = set()
            normalized: list[str] = []
            for item in projected_user_claims:
                if item in seen:
                    continue
                seen.add(item)
                normalized.append(item)
            return normalized
        projected_external: list[str] = []
        for item in list((memory or {}).get("external_evidence") or []):
            if str((item or {}).get("status") or "").strip() not in {"confirmed", "supported"}:
                continue
            content = str((item or {}).get("content") or "").strip()
            if content:
                projected_external.append(content)
        if projected_external:
            seen: set[str] = set()
            normalized: list[str] = []
            for item in projected_external:
                if item in seen:
                    continue
                seen.add(item)
                normalized.append(item)
            return normalized
        return list(
            (memory or {}).get("user_stated_facts")
            or (memory or {}).get("confirmed_facts")
            or []
        )

    @staticmethod
    def _project_evidence_points(memory: dict) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for bucket in (
            list((memory or {}).get("external_evidence") or []),
            list((memory or {}).get("evidence_points") or []),
        ):
            for item in bucket:
                if not isinstance(item, dict):
                    continue
                content = str(item.get("content") or "").strip()
                if not content or content in seen:
                    continue
                seen.add(content)
                merged.append(item)
        return merged

    @staticmethod
    def _clean_phrase(value) -> str:
        return str(value or "").strip()

    @staticmethod
    def _collect_constraint_phrases(memory: dict) -> list[str]:
        constraints = dict((memory or {}).get("constraints") or {})
        phrases: list[str] = []
        for key, value in constraints.items():
            if key == "extra_constraints":
                phrases.extend(list(value or []))
                continue
            if isinstance(value, str):
                phrases.append(value)
        return phrases

    @staticmethod
    def _collect_record_contents(memory: dict, key: str) -> list[str]:
        contents: list[str] = []
        for item in list((memory or {}).get(key) or []):
            if isinstance(item, dict):
                contents.append(item.get("content") or "")
        return contents

    def _collect_relevance_signals(self, *, request, snapshot, memory: dict) -> list[tuple[str, int]]:
        raw_signals: list[tuple[str, int]] = []

        for key in ("current_topics", "user_goals", "confirmed_facts", "teaching_issues", "student_signals", "user_stated_facts"):
            raw_signals.extend((item, self._SIGNAL_WEIGHTS[key]) for item in list(memory.get(key) or []))

        for key in ("user_claims", "external_evidence", "assistant_hypotheses"):
            raw_signals.extend((item, self._SIGNAL_WEIGHTS[key]) for item in self._collect_record_contents(memory, key))

        raw_signals.extend(
            (item, self._SIGNAL_WEIGHTS["constraints"])
            for item in self._collect_constraint_phrases(memory)
        )

        raw_signals.append((getattr(request, "question", "") or "", self._SIGNAL_WEIGHTS["question"]))
        raw_signals.append((getattr(snapshot, "summary", "") or "", self._SIGNAL_WEIGHTS["summary"]))

        normalized: dict[str, int] = {}
        for item, weight in raw_signals:
            phrase = self._clean_phrase(item)
            if not phrase or len(phrase) < 2:
                continue
            normalized[phrase] = max(int(weight), normalized.get(phrase, 0))
        return list(normalized.items())

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

    def _score_message(self, *, message: dict, signals: list[tuple[str, int]]) -> int:
        content = str((message or {}).get("content") or "").strip()
        if not content:
            return 0
        score = 0
        for phrase, weight in signals:
            overlap = self._overlap_score(content, phrase)
            if overlap > 0:
                score += overlap * max(1, int(weight))
        if score > 0 and str((message or {}).get("role") or "").strip() == "user":
            score += 2
        return score

    def _select_relevant_messages(self, *, request, snapshot, memory: dict, limit: int = 6) -> list[dict]:
        raw_messages = list(getattr(snapshot, "recent_messages", []) or [])
        messages = [message for message in raw_messages if self._is_semantic_message(message)]
        if not messages:
            return []

        signals = self._collect_relevance_signals(request=request, snapshot=snapshot, memory=memory)
        scored: list[tuple[int, int, dict]] = []
        for index, message in enumerate(messages):
            score = self._score_message(message=message, signals=signals)
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
            user_goals=list(
                memory.get("user_goals")
                or memory.get("explicit_user_goals")
                or []
            ),
            confirmed_facts=self._project_confirmed_facts(memory),
            constraints=dict(memory.get("constraints") or {}),
            teaching_issues=list(memory.get("teaching_issues") or []),
            student_signals=list(memory.get("student_signals") or []),
            evidence_points=self._project_evidence_points(memory),
            user_claims=list(memory.get("user_claims") or []),
            assistant_hypotheses=list(memory.get("assistant_hypotheses") or []),
            external_evidence=list(memory.get("external_evidence") or []),
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
