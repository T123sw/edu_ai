from __future__ import annotations

import json
import re

from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.domain.extraction_trigger import ExtractionTrigger


class LLMEnhancementProvider:
    _ALLOWED_FIELDS = (
        "summary_text",
        "current_topics",
        "user_goals",
        "constraints",
        "teaching_issues",
        "student_signals",
        "evidence_points",
    )
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

    def __init__(self, *, model_gateway):
        self.model_gateway = model_gateway

    @staticmethod
    def _to_trigger(raw_trigger) -> ExtractionTrigger:
        if isinstance(raw_trigger, ExtractionTrigger):
            return raw_trigger
        return ExtractionTrigger.model_validate(raw_trigger or {})

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        raw = str(text or "").strip()
        fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, flags=re.DOTALL)
        return fenced.group(1).strip() if fenced else raw

    def _build_messages(self, *, trigger: ExtractionTrigger, existing_state: dict, rule_patch: dict, context: dict) -> list[dict]:
        recent_messages = list(context.get("recent_messages") or [])
        compact_messages = [
            {
                "role": str(item.get("role") or ""),
                "content": str(item.get("content") or "")[:240],
            }
            for item in recent_messages[-6:]
            if isinstance(item, dict)
        ]
        payload = {
            "event": trigger.event,
            "question": trigger.question,
            "workflow_type": trigger.workflow_type,
            "existing_state": {
                "conversation_summary": existing_state.get("conversation_summary") or {},
                "conversation_memory": existing_state.get("conversation_memory") or {},
            },
            "rule_patch": rule_patch,
            "context": {
                "resource_type": context.get("resource_type"),
                "action_name": context.get("action_name"),
                "recent_messages": compact_messages,
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是对话状态增强器。"
                    "请只返回 JSON 对象，不要输出解释。"
                    "你只能补充这些字段：summary_text、current_topics、user_goals、constraints、teaching_issues、student_signals、evidence_points。"
                    "不要生成 confirmed_facts、active_context、workflow_state 等运行态字段。"
                    "evidence_points 中每项必须包含 type 和 content，可选 confidence。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

    @staticmethod
    def _normalize_evidence_points(raw_points) -> list[dict]:
        normalized: list[dict] = []
        for item in list(raw_points or []):
            if isinstance(item, str):
                content = item.strip()
                confidence = "medium"
                evidence_type = "observation"
            elif isinstance(item, dict):
                content = str(item.get("content") or "").strip()
                confidence = str(item.get("confidence") or "medium").strip() or "medium"
                evidence_type = str(item.get("type") or "observation").strip() or "observation"
            else:
                continue
            if not content:
                continue
            if confidence not in {"low", "medium", "high"}:
                confidence = "medium"
            normalized.append(
                {
                    "type": evidence_type,
                    "content": content,
                    "source_type": "llm_enhancement",
                    "source_message_ids": [],
                    "confidence": confidence,
                }
            )
        return normalized

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
    def _normalize_semantic_list(cls, raw_values) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in list(raw_values or []):
            value = str(item or "").strip()
            if not value or cls._is_low_signal(value) or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @classmethod
    def _normalize_constraints(cls, raw_constraints) -> dict:
        if not isinstance(raw_constraints, dict):
            return {}
        normalized: dict = {}
        for key in ("audience", "tone", "length", "grade_level", "subject", "course_id"):
            value = str(raw_constraints.get(key) or "").strip()
            if value and not cls._is_low_signal(value):
                normalized[key] = value
        extra_constraints = cls._normalize_semantic_list(raw_constraints.get("extra_constraints") or [])
        if extra_constraints:
            normalized["extra_constraints"] = extra_constraints
        return normalized

    @staticmethod
    def _normalize_candidate_confidence(value) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return "medium"

    def _parse_candidates(self, raw_response: str) -> list[ExtractionCandidate]:
        try:
            payload = json.loads(self._strip_code_fences(raw_response))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            return []

        candidates: list[ExtractionCandidate] = []
        summary_text = str(payload.get("summary_text") or "").strip()
        if summary_text:
            candidates.append(
                ExtractionCandidate(
                    field="summary_text",
                    value=summary_text,
                    source="llm",
                    operation="replace",
                )
            )

        for field in ("current_topics", "user_goals", "teaching_issues", "student_signals"):
            values = self._normalize_semantic_list(payload.get(field) or [])
            if values:
                candidates.append(
                    ExtractionCandidate(
                        field=field,
                        value=values,
                        source="llm",
                        confidence=self._normalize_candidate_confidence(payload.get(f"{field}_confidence")),
                        operation="merge",
                    )
                )

        constraints = self._normalize_constraints(payload.get("constraints") or {})
        if constraints:
            candidates.append(
                ExtractionCandidate(
                    field="constraints",
                    value=constraints,
                    source="llm",
                    confidence=self._normalize_candidate_confidence(payload.get("constraints_confidence")),
                    operation="merge",
                )
            )

        evidence_points = self._normalize_evidence_points(payload.get("evidence_points") or [])
        if evidence_points:
            candidates.append(
                ExtractionCandidate(
                    field="evidence_points",
                    value=evidence_points,
                    source="llm",
                    operation="merge",
                )
            )
        return candidates

    def __call__(self, *, trigger, existing_state: dict, rule_patch: dict, context: dict | None = None) -> list[ExtractionCandidate]:
        normalized_trigger = self._to_trigger(trigger)
        messages = self._build_messages(
            trigger=normalized_trigger,
            existing_state=existing_state,
            rule_patch=rule_patch,
            context=context or {},
        )
        response = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=600)
        return self._parse_candidates(response)
