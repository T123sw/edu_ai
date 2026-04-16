from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.chat.domain.quiz_preparation import QuizPreparationResult
from app.chat.utils.json_utils import extract_json_block


class QuizFollowupPlan(BaseModel):
    ask_needed: bool = False
    question: str = ""
    asked_fields: list[str] = Field(default_factory=list)


class QuizReadinessJudge:
    def __init__(self, *, llm: Any | None = None):
        self.llm = llm

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _has_generation_basis(self, result: QuizPreparationResult) -> bool:
        if int(result.question_count or 0) > 0:
            return True
        if len(list(result.question_types or [])) >= 1:
            return True
        if len(list(result.knowledge_points or [])) >= 1:
            return True
        if len(list(result.weak_points or [])) >= 1:
            return True
        return False

    def _missing_soft_fields(self, result: QuizPreparationResult) -> list[str]:
        missing: list[str] = []
        if int(result.question_count or 0) <= 0:
            missing.append("question_count")
        if not list(result.question_types or []):
            missing.append("question_types")
        if not self._clean(result.difficulty):
            missing.append("difficulty")
        return missing

    def _fallback_question(self, *, action: str, result: QuizPreparationResult) -> tuple[str, list[str]]:
        if action in {"no_quiz_intent", "ask_critical_gap"}:
            return "你想围绕什么内容生成习题？直接告诉我主题就可以。", ["topic"]

        missing_soft_fields = self._missing_soft_fields(result)
        asked_fields = [field for field in ("question_count", "question_types") if field in missing_soft_fields]
        if not asked_fields:
            asked_fields = missing_soft_fields[:2] or ["question_count", "question_types"]

        label_map = {
            "question_count": "题量",
            "question_types": "题型",
            "difficulty": "难度",
        }
        readable_fields = "、".join(label_map.get(field, field) for field in asked_fields[:2])
        return f"我可以直接出题。为了更贴近你的需求，再告诉我{readable_fields}就行。", asked_fields[:2]

    def _build_followup_prompt(
        self,
        *,
        result: QuizPreparationResult,
        action: str,
        critical_fields: list[str],
        optional_fields: list[str],
    ) -> str:
        return (
            "你是习题生成工作流中的追问决策器。你的目标是只在必要时追问，并且一次最多追问 1 到 2 个字段。\n"
            "输出 JSON，字段如下：\n"
            "{\n"
            '  "ask_needed": true/false,\n'
            '  "question": "自然中文追问，最多一句",\n'
            '  "asked_fields": ["topic" | "question_count" | "question_types" | "difficulty"]\n'
            "}\n"
            "规则：\n"
            "1. 如果 topic 缺失，只问 topic，不要顺带再问别的。\n"
            "2. 如果 topic 已有，且已有任一出题依据（题量/题型/知识点/薄弱点），就不要再追问。\n"
            "3. 如果 topic 已有但缺少出题依据，只追问最必要的 1 到 2 个字段，优先 question_count 和 question_types，difficulty 次之。\n"
            "4. 追问不要写成长段解释，不要列清单，不要把所有槽位都问一遍。\n"
            "5. asked_fields 最多 2 个。\n\n"
            f"action={action}\n"
            f"critical_fields={json.dumps(critical_fields, ensure_ascii=False)}\n"
            f"optional_fields={json.dumps(optional_fields, ensure_ascii=False)}\n"
            f"current_result={json.dumps(result.model_dump(exclude_none=True), ensure_ascii=False)}"
        )

    def _plan_followup(
        self,
        *,
        result: QuizPreparationResult,
        action: str,
        critical_fields: list[str],
        optional_fields: list[str],
    ) -> tuple[str, list[str]]:
        if self.llm is not None:
            prompt = self._build_followup_prompt(
                result=result,
                action=action,
                critical_fields=critical_fields,
                optional_fields=optional_fields,
            )
            try:
                structured = self.llm.with_structured_output(QuizFollowupPlan, method="function_calling")
                plan = structured.invoke(prompt)
                if plan and plan.ask_needed and self._clean(plan.question):
                    asked_fields = [self._clean(field) for field in list(plan.asked_fields or []) if self._clean(field)][:2]
                    if critical_fields:
                        asked_fields = [field for field in asked_fields if field in critical_fields] or list(critical_fields[:1])
                    return self._clean(plan.question), asked_fields
            except Exception:
                pass

            try:
                raw = self.llm.invoke(prompt)
                payload = extract_json_block(getattr(raw, "content", raw))
                if isinstance(payload, dict) and payload:
                    plan = QuizFollowupPlan.model_validate(payload)
                    if plan.ask_needed and self._clean(plan.question):
                        asked_fields = [self._clean(field) for field in list(plan.asked_fields or []) if self._clean(field)][:2]
                        if critical_fields:
                            asked_fields = [field for field in asked_fields if field in critical_fields] or list(critical_fields[:1])
                        return self._clean(plan.question), asked_fields
            except Exception:
                pass

        return self._fallback_question(action=action, result=result)

    def judge(self, result: QuizPreparationResult, *, entry_mode: str) -> dict:
        topic = self._clean(result.topic)

        if self._clean(result.quiz_intent) != "generate_quiz":
            question, asked_fields = self._plan_followup(
                result=result,
                action="no_quiz_intent",
                critical_fields=["topic"],
                optional_fields=[],
            )
            return {
                "action": "no_quiz_intent",
                "question": question,
                "asked_fields": asked_fields,
                "missing_critical_fields": [],
            }

        if not topic:
            question, asked_fields = self._plan_followup(
                result=result,
                action="ask_critical_gap",
                critical_fields=["topic"],
                optional_fields=[],
            )
            return {
                "action": "ask_critical_gap",
                "question": question,
                "asked_fields": asked_fields or ["topic"],
                "missing_critical_fields": ["topic"],
            }

        if self._has_generation_basis(result):
            action = "weak_soft_confirm" if self._clean(entry_mode).lower() == "button" else "strong_soft_confirm"
            return {
                "action": action,
                "asked_fields": [],
                "missing_critical_fields": [],
                "soft_confirm_message": self._clean(result.soft_confirm_message),
            }

        optional_fields = self._missing_soft_fields(result)
        question, asked_fields = self._plan_followup(
            result=result,
            action="ask_generation_basis",
            critical_fields=[],
            optional_fields=optional_fields,
        )
        return {
            "action": "ask_generation_basis",
            "question": question,
            "asked_fields": asked_fields[:2],
            "missing_critical_fields": [],
        }
