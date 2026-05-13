from __future__ import annotations

import json

from app.chat.domain.generation_context import GenerationContext


class ReportAssembler:
    _LOW_SIGNAL_TOPIC_PHRASES = {
        "具体一点",
        "详细一点",
        "展开一点",
        "介绍下整个过程",
        "介绍整个过程",
        "整个过程",
        "继续分析",
        "继续生成",
        "请基于当前内容生成一份报告",
        "生成一份报告",
    }

    @staticmethod
    def _first_non_empty(*values) -> str:
        for value in values:
            if isinstance(value, list):
                for item in value:
                    text = str(item or "").strip()
                    if text:
                        return text
                continue
            text = str(value or "").strip()
            if text:
                return text
        return ""

    def _is_low_signal_topic(self, value: str) -> bool:
        normalized = str(value or "").strip()
        if not normalized:
            return True
        if normalized in self._LOW_SIGNAL_TOPIC_PHRASES:
            return True
        if normalized.startswith("比如"):
            return True
        if normalized.endswith("过程") and len(normalized) <= 8:
            return True
        if normalized.endswith("一点") and len(normalized) <= 8:
            return True
        return False

    def _pick_core_topic(self, context: GenerationContext) -> str:
        for topic in list(context.current_topics):
            normalized = str(topic or "").strip()
            if normalized and not self._is_low_signal_topic(normalized):
                return normalized

        for message in list(context.recent_relevant_messages):
            if str((message or {}).get("role") or "").strip() != "user":
                continue
            content = str((message or {}).get("content") or "").strip("。！？!? ")
            if content and not self._is_low_signal_topic(content):
                return content

        return self._first_non_empty(context.summary_text, list(context.confirmed_facts))

    def _build_slot_hints(self, context: GenerationContext) -> dict:
        constraints = dict(context.constraints or {})
        extra_constraints = list(constraints.get("extra_constraints") or [])

        core_topic = self._pick_core_topic(context)
        focus_area = self._first_non_empty(
            list(context.teaching_issues),
            list(context.student_signals),
            list(context.confirmed_facts),
        )

        depth_level = ""
        if any("深入" in item or "详细" in item for item in extra_constraints):
            depth_level = "深入分析"
        elif any("简要" in item or "简短" in item for item in extra_constraints):
            depth_level = "简明分析"

        format_style = ""
        if any("提纲" in item or "大纲" in item for item in extra_constraints):
            format_style = "提纲式分析报告"
        elif str(constraints.get("tone") or "").strip() == "正式" or str(constraints.get("audience") or "").strip() == "教研组":
            format_style = "正式分析报告"

        dynamic_constraints_payload = {
            "audience": str(constraints.get("audience") or "").strip(),
            "tone": str(constraints.get("tone") or "").strip(),
            "grade_level": str(constraints.get("grade_level") or "").strip(),
            "subject": str(constraints.get("subject") or "").strip(),
            "extra_constraints": [str(item or "").strip() for item in extra_constraints if str(item or "").strip()],
        }
        dynamic_constraints_payload = {
            key: value
            for key, value in dynamic_constraints_payload.items()
            if value is not None and value != "" and value != []
        }

        return {
            "core_topic": core_topic,
            "focus_area": focus_area,
            "length_requirement": str(constraints.get("length") or "").strip(),
            "depth_level": depth_level,
            "format_style": format_style,
            "dynamic_constraints": json.dumps(dynamic_constraints_payload, ensure_ascii=False) if dynamic_constraints_payload else "",
        }

    def _build_context_digest(self, context: GenerationContext) -> str:
        parts: list[str] = []
        if context.summary_text:
            parts.append(f"摘要：{context.summary_text}")
        if context.current_topics:
            parts.append(f"主题：{'、'.join(context.current_topics[:3])}")
        if context.teaching_issues:
            parts.append(f"问题：{'、'.join(context.teaching_issues[:3])}")
        if context.student_signals:
            parts.append(f"学生信号：{'、'.join(context.student_signals[:3])}")
        if context.confirmed_facts:
            parts.append(f"已确认事实：{'；'.join(context.confirmed_facts[:2])}")
        evidence_contents = [
            str(item.get("content") or "").strip()
            for item in list(context.evidence_points or [])
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ]
        if evidence_contents:
            parts.append(f"观察证据：{'；'.join(evidence_contents[:2])}")
        return "\n".join(parts)

    def from_generation_context(self, context: GenerationContext) -> dict:
        active_artifact = None
        if context.active_artifact_id:
            active_artifact = {
                "artifact_id": context.active_artifact_id,
                "artifact_type": context.active_artifact_type,
            }
        slot_hints = self._build_slot_hints(context)
        return {
            "summary": context.summary_text,
            "current_topics": list(context.current_topics),
            "user_goals": list(context.user_goals),
            "confirmed_facts": list(context.confirmed_facts),
            "constraints": dict(context.constraints),
            "teaching_issues": list(context.teaching_issues),
            "student_signals": list(context.student_signals),
            "evidence_points": list(context.evidence_points),
            "recent_messages": list(context.recent_relevant_messages),
            "active_artifact": active_artifact,
            "current_course_id": context.current_course_id,
            "referenced_artifact_ids": list(context.referenced_artifact_ids),
            "source_scope": dict(context.source_scope),
            "slot_hints": slot_hints,
            "context_digest": self._build_context_digest(context),
        }
