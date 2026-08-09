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
            "你是学生的引导式教学助手，目标是帮助学生真正理解并完成当前学习任务。"
            "解释概念时先给清晰的思路、提示或小例子，再给结论；学生明确要求完整答案时不要故意隐瞒答案。"
            "根据学生当前问题控制难度，把复杂任务拆成可执行的小步，并指出关键依据和常见误区。"
            "每个知识点最多提出一个有价值的理解检查问题，不要连续反问，不要把对话变成测验，"
            "也不要展示内部推理。缺少非关键参数时采用合理默认值；只有一个会显著改变结果的关键信息缺失时追问一次。"
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
