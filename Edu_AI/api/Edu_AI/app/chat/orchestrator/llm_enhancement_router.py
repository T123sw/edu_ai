from __future__ import annotations

from app.chat.domain.extraction_trigger import ExtractionTrigger
from app.chat.orchestrator.extraction_guard import ExtractionGuard


class LLMEnhancementRouter:
    DEFAULT_TRIGGER_EVENTS = {
        "reply.completed",
        "workflow.report.requested",
        "workflow.lesson_plan.requested",
        "workflow.quiz.requested",
        "workflow.ppt.requested",
    }

    def __init__(
        self,
        *,
        enabled: bool = False,
        enhancer=None,
        guard: ExtractionGuard | None = None,
        trigger_events: set[str] | None = None,
    ):
        self.enabled = bool(enabled and callable(enhancer))
        self.enhancer = enhancer
        self.guard = guard or ExtractionGuard()
        self.trigger_events = set(trigger_events or self.DEFAULT_TRIGGER_EVENTS)

    def should_run(self, trigger: ExtractionTrigger) -> bool:
        return self.enabled and trigger.event in self.trigger_events

    @staticmethod
    def _base_observation(*, trigger: ExtractionTrigger, rule_patch: dict) -> dict:
        return {
            "trigger_event": trigger.event,
            "candidate_fields": [],
            "accepted_fields": [],
            "rejected_fields": [],
            "fallback_reason": None,
            "final_patch": {
                "summary_text": str(((rule_patch.get("conversation_summary") or {}).get("summary_text")) or ""),
                "memory": dict(rule_patch.get("conversation_memory") or {}),
            },
        }

    def apply_with_observation(self, *, trigger: ExtractionTrigger, existing_state: dict, rule_patch: dict, context: dict | None = None) -> tuple[dict, dict]:
        observation = self._base_observation(trigger=trigger, rule_patch=rule_patch)
        if not self.enabled:
            observation["fallback_reason"] = "disabled"
            return rule_patch, observation
        if trigger.event not in self.trigger_events:
            observation["fallback_reason"] = "unsupported_trigger"
            return rule_patch, observation

        try:
            candidates = self.enhancer(
                trigger=trigger,
                existing_state=existing_state,
                rule_patch=rule_patch,
                context=context or {},
            )
        except Exception:
            observation["fallback_reason"] = "enhancer_error"
            return rule_patch, observation
        merged_patch, guard_report = self.guard.merge_with_report(
            existing_state=existing_state,
            rule_patch=rule_patch,
            candidates=candidates or [],
        )
        observation.update(guard_report)
        return merged_patch, observation

    def apply(self, *, trigger: ExtractionTrigger, existing_state: dict, rule_patch: dict, context: dict | None = None) -> dict:
        merged_patch, _ = self.apply_with_observation(
            trigger=trigger,
            existing_state=existing_state,
            rule_patch=rule_patch,
            context=context,
        )
        return merged_patch
