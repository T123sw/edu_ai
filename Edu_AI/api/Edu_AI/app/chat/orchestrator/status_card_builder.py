from __future__ import annotations

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.status_card import StatusCardViewModel

from .status_card_label_mapper import StatusCardLabelMapper


class StatusCardBuilder:
    def __init__(self, *, label_mapper: StatusCardLabelMapper | None = None):
        self.label_mapper = label_mapper or StatusCardLabelMapper()

    @staticmethod
    def _coerce_workflow(snapshot, workflow):
        if workflow:
            return dict(workflow)
        workflow_state = getattr(snapshot, "workflow_state", None)
        if workflow_state is None:
            return {}
        if hasattr(workflow_state, "model_dump"):
            raw = workflow_state.model_dump()
            return {
                "type": raw.get("workflow_type"),
                "status": raw.get("status"),
                "phase": raw.get("stage"),
                "required_slots": raw.get("required_slots") or [],
            }
        return dict(workflow_state or {})

    @staticmethod
    def _coerce_capability(snapshot, capability):
        if capability is not None:
            return capability
        return getattr(snapshot, "capability", None) or CapabilityPolicy()

    @staticmethod
    def _truncate(value: str, limit: int = 60) -> str:
        value = str(value or "").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "…"

    def build(self, *, snapshot, workflow=None, capability=None) -> StatusCardViewModel:
        snapshot = snapshot or type("Snapshot", (), {})()
        memory = dict(getattr(snapshot, "conversation_memory", {}) or {})
        active_context = dict(getattr(snapshot, "active_context", {}) or {})
        workflow = self._coerce_workflow(snapshot, workflow)
        capability = self._coerce_capability(snapshot, capability)

        workflow_type = workflow.get("type") or active_context.get("active_workflow_type")
        workflow_status = workflow.get("status") or active_context.get("active_workflow_status")
        phase = workflow.get("phase") or workflow.get("stage")
        required_slots = list(workflow.get("required_slots") or [])
        mode = "workflow" if workflow_type and workflow_status in {"running", "awaiting_confirm"} else "chat"

        topics = list(memory.get("current_topics") or [])[:3]
        issues = list(memory.get("teaching_issues") or memory.get("student_signals") or [])[:3]
        confirmed_facts = list(memory.get("confirmed_facts") or [])[:3]
        student_signals = list(memory.get("student_signals") or [])[:4]
        raw_evidence_points = list(memory.get("evidence_points") or [])
        evidence_points = [
            str(item.get("content") or "").strip()
            for item in raw_evidence_points
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ][:4]
        evidence_details = [
            {
                "content": str(item.get("content") or "").strip(),
                "source_type": str(item.get("source_type") or "assistant_message"),
                "confidence": str(item.get("confidence") or "low"),
                "source_message_count": len(list(item.get("source_message_ids") or [])),
            }
            for item in raw_evidence_points
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ][:4]
        constraints = dict(memory.get("constraints") or {})
        extra_constraints = list(constraints.get("extra_constraints") or [])[:4]
        selected_doc_ids = list(active_context.get("pinned_doc_ids") or getattr(capability, "selected_doc_ids", []) or [])

        source_labels = ["当前会话"]
        if selected_doc_ids:
            source_labels.append(f"已选文档 {len(selected_doc_ids)} 份")
        if active_context.get("current_course_id"):
            source_labels.append("当前课程")

        active_artifact_type = active_context.get("active_artifact_type") or getattr(getattr(snapshot, "active_artifact", None), "artifact_type", None)
        active_artifact_id = active_context.get("active_artifact_id") or getattr(getattr(snapshot, "active_artifact", None), "artifact_id", None)
        active_artifact_label = None
        if active_artifact_type or active_artifact_id:
            workflow_label = self.label_mapper.map_workflow_label(active_artifact_type) or "产物"
            active_artifact_label = f"当前产物：{workflow_label}"

        goal = (
            self.label_mapper.map_workflow_goal(workflow_type)
            or self.label_mapper.map_workflow_goal(active_context.get("active_workflow_type"))
            or next(iter(memory.get("user_goals") or []), None)
        )

        status_label = self.label_mapper.map_status(
            workflow_type=workflow_type,
            status=workflow_status,
            phase=phase,
            required_slots=required_slots,
        )
        waiting_label = self.label_mapper.map_waiting_label(
            workflow_type=workflow_type,
            status=workflow_status,
            phase=phase,
            required_slots=required_slots,
        )
        suggested_actions = self.label_mapper.map_suggested_actions(
            workflow_type=workflow_type,
            status=workflow_status,
            required_slots=required_slots,
        )
        summary = str(getattr(snapshot, "summary", "") or "")
        summary_hint = None
        if summary and (not topics or not goal or not issues):
            summary_hint = self._truncate(summary)

        card = StatusCardViewModel(
            mode=mode,
            status_label=status_label if mode == "workflow" else "普通对话",
            workflow_label=self.label_mapper.map_workflow_label(workflow_type),
            topics=topics,
            goal=goal,
            issues=issues,
            confirmed_facts=confirmed_facts,
            student_signals=student_signals,
            evidence_points=evidence_points,
            evidence_details=evidence_details,
            extra_constraints=extra_constraints,
            source_labels=source_labels,
            active_artifact_label=active_artifact_label,
            waiting_label=waiting_label,
            suggested_actions=suggested_actions if mode == "workflow" or topics or goal or issues else ["继续提问", "生成报告"],
            audience=constraints.get("audience"),
            tone=constraints.get("tone"),
            length=constraints.get("length"),
            grade_level=constraints.get("grade_level"),
            subject=constraints.get("subject"),
            allow_rag=bool(getattr(capability, "allow_rag", False)),
            allow_web=bool(getattr(capability, "allow_web", False)),
            summary_hint=summary_hint,
        )
        if mode == "chat" and not waiting_label:
            card.waiting_label = "继续提问，或告诉我你想生成什么"
        return card
