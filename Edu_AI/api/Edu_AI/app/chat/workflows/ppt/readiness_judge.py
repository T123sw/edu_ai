from __future__ import annotations

from app.chat.domain.ppt_preparation import PptPreparationResult


class PptReadinessJudge:
    _ASSUMPTION_BY_FIELD = {
        "topic": "默认使用当前对话主题作为 PPT 主题。",
        "audience": "如果受众不清晰，则默认按通用学习者处理。",
        "objective": "如果目标不清晰，则默认按课堂讲解型 PPT 处理。",
        "key_points": "从当前对话中归纳 2 到 4 个重点内容页。",
    }

    _QUESTION_BY_FIELD = {
        "topic": "这份 PPT 主要想讲哪个主题？",
        "audience": "这份 PPT 主要面向哪类学生或听众？",
        "objective": "你希望这份 PPT 更偏课堂讲解、汇报展示，还是复习总结？",
        "key_points": "你最希望这份 PPT 重点覆盖哪 2 到 4 个部分？",
    }

    def _missing_core_fields(self, preparation: PptPreparationResult) -> list[str]:
        missing = list(preparation.missing_core_fields or [])
        if missing:
            return missing

        computed: list[str] = []
        if not str(preparation.topic or "").strip():
            computed.append("topic")
        if not str(preparation.audience or "").strip():
            computed.append("audience")
        if not str(preparation.objective or "").strip():
            computed.append("objective")
        if len(list(preparation.key_points or [])) < 2:
            computed.append("key_points")
        return computed

    def _build_assumptions(self, missing_fields: list[str]) -> list[str]:
        return [self._ASSUMPTION_BY_FIELD[field] for field in missing_fields if field in self._ASSUMPTION_BY_FIELD]

    def judge(self, preparation: PptPreparationResult, *, followup_rounds: int) -> dict:
        missing_fields = self._missing_core_fields(preparation)
        if not missing_fields:
            return {
                "action": "generate_outline",
                "question": "",
                "followup_question": "",
                "required_slots": [],
                "missing_core_fields": [],
                "assumptions": [],
            }

        has_topic = bool(str(preparation.topic or "").strip())
        has_audience = bool(str(preparation.audience or "").strip())
        has_objective = bool(str(preparation.objective or "").strip())
        key_point_count = len(list(preparation.key_points or []))
        has_rich_key_points = key_point_count >= 2

        if has_topic and has_rich_key_points and (has_objective or has_audience):
            return {
                "action": "generate_outline",
                "question": "",
                "followup_question": "",
                "required_slots": missing_fields,
                "missing_core_fields": missing_fields,
                "assumptions": self._build_assumptions(missing_fields),
            }

        if int(followup_rounds or 0) >= 2:
            return {
                "action": "generate_outline",
                "question": "",
                "followup_question": "",
                "required_slots": missing_fields,
                "missing_core_fields": missing_fields,
                "assumptions": self._build_assumptions(missing_fields),
            }

        first_missing = missing_fields[0]
        question = self._QUESTION_BY_FIELD.get(first_missing, "这份 PPT 还缺少哪一项关键信息？")
        return {
            "action": "ask_followup",
            "question": question,
            "followup_question": question,
            "required_slots": [first_missing],
            "missing_core_fields": missing_fields,
            "assumptions": [],
        }
