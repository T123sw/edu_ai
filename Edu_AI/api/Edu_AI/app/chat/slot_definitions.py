from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, Field


class BaseSlots(BaseModel):
    """所有资源类型共享的基础槽位。"""

    topic: str = ""
    audience: str = ""
    objective: str = ""


class ReportSlots(BaseSlots):
    focus_area: str = ""
    length_requirement: str = ""
    depth_level: str = ""
    format_style: str = ""
    dynamic_constraints: str = ""

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "focus_area"]
        secondary_slots: ClassVar[List[str]] = ["length_requirement", "depth_level", "format_style", "dynamic_constraints"]
        defaults: ClassVar[Dict[str, Any]] = {
            "length_requirement": "1500-2500字",
            "depth_level": "中等",
            "format_style": "markdown",
            "dynamic_constraints": "",
        }


class LessonPlanSlots(BaseSlots):
    duration: str = ""
    teaching_method: str = ""
    key_points: str = ""
    assessment_method: str = ""

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "duration"]
        secondary_slots: ClassVar[List[str]] = ["teaching_method", "key_points", "assessment_method"]
        defaults: ClassVar[Dict[str, Any]] = {
            "duration": "45分钟",
            "teaching_method": "讲练结合",
            "key_points": "",
            "assessment_method": "课堂提问+随堂练习",
        }


class QuizSlots(BaseSlots):
    difficulty: str = ""
    question_count: int = 10
    question_types: List[str] = Field(default_factory=lambda: ["单选题"])
    include_answers: bool = True

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "difficulty"]
        secondary_slots: ClassVar[List[str]] = ["question_count", "question_types", "include_answers"]
        defaults: ClassVar[Dict[str, Any]] = {
            "difficulty": "中等",
            "question_count": 10,
            "question_types": ["单选题"],
            "include_answers": True,
        }


class FlashcardSlots(BaseSlots):
    card_count: int = 20
    card_style: str = "问答式"

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective"]
        secondary_slots: ClassVar[List[str]] = ["card_count", "card_style"]
        defaults: ClassVar[Dict[str, Any]] = {
            "card_count": 20,
            "card_style": "问答式",
        }


class BlogSlots(BaseSlots):
    blog_length: str = ""
    writing_tone: str = ""
    include_tables: bool = False

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "blog_length"]
        secondary_slots: ClassVar[List[str]] = ["writing_tone", "include_tables"]
        defaults: ClassVar[Dict[str, Any]] = {
            "blog_length": "1200-1800字",
            "writing_tone": "专业但易懂",
            "include_tables": False,
        }


class PPTSlots(BaseSlots):
    slide_count: int = 12
    template_style: str = "教学简洁风"
    include_notes: bool = True
    visual_preference: str = "图文并茂"

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "slide_count"]
        secondary_slots: ClassVar[List[str]] = ["template_style", "include_notes", "visual_preference"]
        defaults: ClassVar[Dict[str, Any]] = {
            "slide_count": 12,
            "template_style": "教学简洁风",
            "include_notes": True,
            "visual_preference": "图文并茂",
        }


class VideoSlots(BaseSlots):
    video_duration: str = ""
    video_type: str = ""
    narration_style: str = ""

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "video_duration"]
        secondary_slots: ClassVar[List[str]] = ["video_type", "narration_style"]
        defaults: ClassVar[Dict[str, Any]] = {
            "video_duration": "5-8分钟",
            "video_type": "讲解型",
            "narration_style": "清晰自然",
        }


class PodcastSlots(BaseSlots):
    podcast_duration: str = ""
    podcast_format: str = ""
    tone: str = ""

    class SlotMeta:
        core_slots: ClassVar[List[str]] = ["topic", "audience", "objective", "podcast_duration"]
        secondary_slots: ClassVar[List[str]] = ["podcast_format", "tone"]
        defaults: ClassVar[Dict[str, Any]] = {
            "podcast_duration": "10-15分钟",
            "podcast_format": "单人讲述",
            "tone": "亲切专业",
        }


SlotModel = Type[BaseSlots]

SLOT_REGISTRY: Dict[str, SlotModel] = {
    "report": ReportSlots,
    "lesson_plan": LessonPlanSlots,
    "quiz": QuizSlots,
    "flashcard": FlashcardSlots,
    "blog": BlogSlots,
    "ppt": PPTSlots,
    "video": VideoSlots,
    "podcast": PodcastSlots,
}


def get_slot_model(resource_type: str) -> Optional[SlotModel]:
    return SLOT_REGISTRY.get(resource_type)
