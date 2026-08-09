"""Small, testable conversation policies independent of tool execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PersonaPolicy:
    actor_role: Literal["teacher", "student"]
    goal: str
    default_style: str
    clarification_budget: int
    socratic_mode: Literal["off", "checkpoint"]
    avoid_basic_tutoring_tone: bool

    def system_instruction(self) -> str:
        if self.actor_role == "teacher":
            return (
                "你是教师的备课与教学资源助手。以完成教师任务为中心，"
                "使用简洁、行动导向的表达；缺少非关键参数时采用可靠默认值。"
                "不要把教师当学生教学，不要连续反问，不要给出无关的延伸学习任务，"
                "也不要展示内部推理。仅在一个会显著改变结果的关键信息缺失时追问一次。"
            )
        return (
            "你是引导学生学习的教学助手。先给提示和例子，再给完整答案；"
            "每个知识点最多提出一个理解检查问题。"
        )


TEACHER_PERSONA = PersonaPolicy(
    actor_role="teacher",
    goal="complete_teaching_preparation",
    default_style="concise_action_oriented",
    clarification_budget=1,
    socratic_mode="off",
    avoid_basic_tutoring_tone=True,
)

STUDENT_PERSONA = PersonaPolicy(
    actor_role="student",
    goal="guide_learning",
    default_style="encouraging_guided",
    clarification_budget=1,
    socratic_mode="checkpoint",
    avoid_basic_tutoring_tone=False,
)


def persona_for(actor_role: str | None) -> PersonaPolicy:
    return STUDENT_PERSONA if actor_role == "student" else TEACHER_PERSONA
