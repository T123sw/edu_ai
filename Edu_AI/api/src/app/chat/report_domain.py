from __future__ import annotations

from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field

REPORT_SLOT_KEYS = [
    "core_topic",
    "focus_area",
    "length_requirement",
    "depth_level",
    "format_style",
    "dynamic_constraints",
]

REPORT_SLOT_PRIORITY = [
    "core_topic",
    "focus_area",
    "length_requirement",
    "depth_level",
    "format_style",
]

REPORT_DEFAULTS = {
    "report_type": "通用分析报告",
    "core_topic": "未指定主题",
    "focus_area": "基础概览",
    "length_requirement": "常规长度（约3-4章）",
    "depth_level": "标准研报级（逻辑严密、可读）",
    "format_style": "结构化分块论述",
}

REPORT_IMPATIENT_KEYWORDS = [
    "现在生成",
    "现在就生成",
    "不用问",
    "别问",
    "快点",
    "尽快",
    "直接生成",
    "马上生成",
    "立刻生成",
    "够了",
    "行了",
    "不用再问",
    "别再问",
]


class ExtractedIntent(BaseModel):
    teaching_target: Optional[str] = Field(
        default=None,
        description=(
            "教学目标。用户可能不会直接说'目标是...'，若用户说'讲讲生平'或'介绍一下'，"
            "请总结为正式教学目标，例如'了解XXX的生平事迹'，绝不要机械留空。"
        ),
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="目标受众或年级，如大一学生、高三复习班。",
    )
    course_duration: Optional[str] = Field(
        default=None,
        description="课程时长。如果用户提到'微课'，推断为'10-15分钟'。",
    )


class AgentChatResponse(BaseModel):
    internal_monologue: Any = Field(
        default="",
        description=(
            "【仅供系统内部使用】请先反思：1) 用户真实意图与情绪；"
            "2) 当前是否已有工具或检索结果可用；"
            "3) 本轮应偏解答还是偏启发。"
        ),
    )
    user_reply: Any = Field(
        default="",
        description="【对用户可见】最终回复内容，遵守系统语气与格式要求。",
    )


class AgentGenerateResponse(BaseModel):
    internal_monologue: Any = Field(
        default="",
        description=(
            "【仅供系统内部使用】请先反思：1) 正文是否严格贴合大纲；"
            "2) 是否覆盖目标受众与目标；3) 是否存在结构/表达缺陷。"
        ),
    )
    final_content: Any = Field(
        default="",
        description="【对用户可见】最终正文内容，要求结构完整、可执行。",
    )


class TaskStateUpdateIntent(BaseModel):
    thought_process: Optional[str] = Field(
        default="",
        description=(
            "状态追踪反思：分析用户的真实意图（补充、修改、强制生成、或闲聊），"
            "并指出本轮哪些字段发生更新或需要覆盖。"
        )
    )
    user_intent: Optional[str] = Field(
        default="provide",
        description=(
            "用户核心意图：provide=补充; modify=修改; force_generate=强制生成; "
            "confirm_outline=确认大纲后生成; chitchat=无关闲聊。若无法判断，默认 provide。"
        ),
    )
    profile_subject: Optional[str] = Field(default=None, description="教师任教科目。")
    profile_grade: Optional[str] = Field(default=None, description="教师年级或受众。")
    profile_style: Optional[str] = Field(default=None, description="教师偏好风格。")

    # v5.1 report slots
    core_topic: Optional[str] = Field(default=None, description="核心主题。")
    focus_area: Optional[str] = Field(default=None, description="聚焦方向。")
    length_requirement: Optional[str] = Field(default=None, description="长度要求。")
    depth_level: Optional[str] = Field(default=None, description="深度层级。")
    format_style: Optional[str] = Field(default=None, description="文风/格式风格。")
    dynamic_constraints: Optional[str] = Field(default=None, description="动态约束（JSON字符串或文本）。")
