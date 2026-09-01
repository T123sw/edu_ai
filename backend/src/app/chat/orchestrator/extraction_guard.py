from __future__ import annotations

from app.chat.domain.extraction_candidate import ExtractionCandidate


class ExtractionGuard:
    _LIST_FIELDS = {
        "current_topics",
        "user_goals",
        "confirmed_facts",
        "teaching_issues",
        "student_signals",
    }
    _PROTECTED_LLM_FIELDS = {
        "confirmed_facts",
        "active_context",
        "capability_policy",
        "workflow_state",
        "selected_doc_ids",
        "current_course_id",
        "active_artifact_id",
        "active_artifact_type",
    }
    _LOW_SIGNAL_VALUES = {
        "",
        "继续",
        "继续分析",
        "继续对话",
        "继续生成",
        "详细一点",
        "展开一点",
        "具体一点",
        "当前内容",
        "当前上下文",
        "生成报告",
        "生成一份报告",
        "帮我生成一份报告",
    }

    @staticmethod
    def _dedupe_keep_order(values: list[str], *, limit: int = 6) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _is_low_signal(cls, value: str) -> bool:
        normalized = str(value or "").strip()
        if not normalized:
            return True
        if normalized in cls._LOW_SIGNAL_VALUES:
            return True
        if normalized.startswith("请基于当前内容生成"):
            return True
        if normalized.endswith("一点") and len(normalized) <= 8:
            return True
        return False

    @classmethod
    def _sanitize_list_candidate(cls, *, field: str, values: list[str]) -> list[str]:
        sanitized: list[str] = []
        for value in list(values or []):
            normalized = str(value or "").strip()
            if not normalized:
                continue
            if field in {"current_topics", "user_goals"} and cls._is_low_signal(normalized):
                continue
            sanitized.append(normalized)
        return cls._dedupe_keep_order(sanitized, limit=max(len(sanitized), 1))

    @classmethod
    def _sanitize_constraints_candidate(cls, value: dict) -> dict:
        if not isinstance(value, dict):
            return {}
        normalized: dict = {}
        for key, raw in value.items():
            if key == "extra_constraints":
                continue
            text = str(raw or "").strip()
            if text and not cls._is_low_signal(text):
                normalized[key] = text
        extra_constraints = cls._sanitize_list_candidate(
            field="constraints",
            values=list(value.get("extra_constraints") or []),
        )
        extra_constraints = [item for item in extra_constraints if not cls._is_low_signal(item)]
        if extra_constraints:
            normalized["extra_constraints"] = extra_constraints
        return normalized

    @staticmethod
    def _merge_source_message_ids(existing_ids: list[str], new_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for value in list(existing_ids or []) + list(new_ids or []):
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    @staticmethod
    def _confidence_for_source_count(count: int) -> str:
        if count >= 3:
            return "high"
        if count >= 2:
            return "medium"
        return "low"

    def _merge_evidence_points(self, existing_points: list[dict], new_points: list[dict], *, limit: int = 5) -> list[dict]:
        merged_by_content: dict[str, dict] = {}
        order: list[str] = []

        for item in list(existing_points or []) + list(new_points or []):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            if content not in merged_by_content:
                source_ids = list(item.get("source_message_ids") or [])
                merged_by_content[content] = {
                    "type": str(item.get("type") or "observation"),
                    "content": content,
                    "source_type": str(item.get("source_type") or "assistant_message"),
                    "source_message_ids": source_ids,
                    "confidence": str(item.get("confidence") or self._confidence_for_source_count(len(source_ids))),
                }
                order.append(content)
                continue

            current = merged_by_content[content]
            current_ids = self._merge_source_message_ids(
                list(current.get("source_message_ids") or []),
                list(item.get("source_message_ids") or []),
            )
            current["source_message_ids"] = current_ids
            current["confidence"] = self._confidence_for_source_count(len(current_ids))

        return [merged_by_content[content] for content in order][:limit]

    @staticmethod
    def _dedupe_fields(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _summarize_patch(patch: dict) -> dict:
        summary = dict((patch or {}).get("conversation_summary") or {})
        memory = dict((patch or {}).get("conversation_memory") or {})
        memory_summary: dict[str, object] = {}
        for key, value in memory.items():
            if isinstance(value, list):
                if key == "evidence_points":
                    memory_summary[key] = [str(item.get("content") or "").strip() for item in value if isinstance(item, dict)][:2]
                else:
                    memory_summary[key] = [str(item or "").strip() for item in value][:3]
            elif isinstance(value, dict):
                compact = dict(value)
                if "extra_constraints" in compact:
                    compact["extra_constraints"] = list(compact.get("extra_constraints") or [])[:3]
                memory_summary[key] = compact
            else:
                memory_summary[key] = value
        return {
            "summary_text": str(summary.get("summary_text") or ""),
            "memory": memory_summary,
        }

    def merge_with_report(self, *, existing_state: dict, rule_patch: dict, candidates: list[ExtractionCandidate | dict] | None) -> tuple[dict, dict]:
        merged_patch = dict(rule_patch or {})
        summary_patch = dict(merged_patch.get("conversation_summary") or {})
        memory_patch = dict(merged_patch.get("conversation_memory") or {})

        existing_summary = dict(existing_state.get("conversation_summary") or {})
        existing_memory = dict(existing_state.get("conversation_memory") or {})
        candidate_fields: list[str] = []
        accepted_fields: list[str] = []
        rejected_fields: list[str] = []

        if "summary_text" not in summary_patch and existing_summary.get("summary_text"):
            summary_patch["summary_text"] = existing_summary.get("summary_text")

        for raw_candidate in list(candidates or []):
            candidate = raw_candidate if isinstance(raw_candidate, ExtractionCandidate) else ExtractionCandidate.model_validate(raw_candidate)
            candidate_fields.append(candidate.field)
            if candidate.source == "llm" and candidate.field in self._PROTECTED_LLM_FIELDS:
                rejected_fields.append(candidate.field)
                continue
            if candidate.source == "llm" and candidate.confidence == "low" and candidate.field in {"current_topics", "user_goals", "constraints"}:
                rejected_fields.append(candidate.field)
                continue

            if candidate.field == "summary_text":
                summary_patch["summary_text"] = str(candidate.value or "").strip() or summary_patch.get("summary_text") or ""
                accepted_fields.append(candidate.field)
                continue

            if candidate.field in self._LIST_FIELDS:
                incoming = self._sanitize_list_candidate(
                    field=candidate.field,
                    values=[str(item or "").strip() for item in list(candidate.value or [])],
                )
                if not incoming:
                    rejected_fields.append(candidate.field)
                    continue
                current = list(memory_patch.get(candidate.field) or existing_memory.get(candidate.field) or [])
                if candidate.operation == "replace":
                    memory_patch[candidate.field] = self._dedupe_keep_order(incoming, limit=max(len(incoming), 1))
                else:
                    memory_patch[candidate.field] = self._dedupe_keep_order(incoming + current, limit=max(len(incoming + current), 1))
                accepted_fields.append(candidate.field)
                continue

            if candidate.field == "constraints":
                current_constraints = dict(memory_patch.get("constraints") or existing_memory.get("constraints") or {})
                incoming_constraints = self._sanitize_constraints_candidate(dict(candidate.value or {}))
                if not incoming_constraints:
                    rejected_fields.append(candidate.field)
                    continue
                extra_constraints = self._dedupe_keep_order(
                    list(incoming_constraints.get("extra_constraints") or [])
                    + list(current_constraints.get("extra_constraints") or []),
                    limit=6,
                )
                merged_constraints = {
                    **current_constraints,
                    **{key: value for key, value in incoming_constraints.items() if key != "extra_constraints"},
                    "extra_constraints": extra_constraints,
                }
                memory_patch["constraints"] = merged_constraints
                accepted_fields.append(candidate.field)
                continue

            if candidate.field == "evidence_points":
                current_points = list(memory_patch.get("evidence_points") or existing_memory.get("evidence_points") or [])
                incoming_points = list(candidate.value or [])
                memory_patch["evidence_points"] = self._merge_evidence_points(current_points, incoming_points)
                accepted_fields.append(candidate.field)
                continue

            rejected_fields.append(candidate.field)

        if summary_patch:
            merged_patch["conversation_summary"] = summary_patch
        if memory_patch:
            merged_patch["conversation_memory"] = memory_patch
        report = {
            "candidate_fields": self._dedupe_fields(candidate_fields),
            "accepted_fields": self._dedupe_fields(accepted_fields),
            "rejected_fields": self._dedupe_fields(rejected_fields),
            "final_patch": self._summarize_patch(merged_patch),
        }
        return merged_patch, report

    def merge(self, *, existing_state: dict, rule_patch: dict, candidates: list[ExtractionCandidate | dict] | None) -> dict:
        merged_patch, _ = self.merge_with_report(
            existing_state=existing_state,
            rule_patch=rule_patch,
            candidates=candidates,
        )
        return merged_patch
