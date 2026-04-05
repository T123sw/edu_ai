from __future__ import annotations

import json
import re

from app.chat.domain.extraction_candidate import ExtractionCandidate
from app.chat.domain.extraction_trigger import ExtractionTrigger


class LLMEnhancementProvider:
    _ALLOWED_FIELDS = (
        "summary_text",
        "teaching_issues",
        "student_signals",
        "evidence_points",
    )

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
                    "你只能补充四类字段：summary_text、teaching_issues、student_signals、evidence_points。"
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

        for field in ("teaching_issues", "student_signals"):
            values = [str(item or "").strip() for item in list(payload.get(field) or [])]
            values = [value for value in values if value]
            if values:
                candidates.append(
                    ExtractionCandidate(
                        field=field,
                        value=values,
                        source="llm",
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
