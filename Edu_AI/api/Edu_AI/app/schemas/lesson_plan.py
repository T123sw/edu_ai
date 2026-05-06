from typing import List, Optional

from pydantic import BaseModel, Field


class LessonPlanRequest(BaseModel):
    topic: str = Field(..., description="Lesson topic")
    course_id: Optional[str] = Field(None, description="Course ID")
    selected_doc_ids: List[str] = Field(..., description="Selected document ids")
    duration: int = Field(45, description="Lesson duration")
    difficulty: str = Field("medium", description="Difficulty")
    knowledge_points: List[str] = Field(default_factory=list, description="Knowledge points")
    key_points: Optional[str] = Field(None, description="Key points")
    hard_points: Optional[str] = Field(None, description="Hard points")


class LessonPlanStep(BaseModel):
    step: str
    content: str
    duration: str


class LessonPlanResponse(BaseModel):
    id: Optional[str] = None
    title: str
    objectives: List[str]
    keyPoints: List[str]
    hardPoints: List[str]
    process: List[LessonPlanStep]
    homework: str


class LessonPlanMeta(BaseModel):
    id: str
    title: str
    topic: str
    difficulty: str
    knowledge_points: List[str]
    created_at: str
    updated_at: str


class LessonPlanListResponse(BaseModel):
    plans: List[LessonPlanMeta]
    count: int

