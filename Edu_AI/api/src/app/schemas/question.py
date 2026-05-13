from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgePointsRequest(BaseModel):
    course_name: str = Field(..., description="Course name")


class KnowledgePointsResponse(BaseModel):
    knowledge_points: List[str]


class QuestionItem(BaseModel):
    id: int
    type: str
    difficulty: str
    content: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None


class QuestionGenerateRequest(BaseModel):
    knowledge_points: List[str] = Field(default_factory=list, description="Knowledge points")
    types: List[str] = Field(default_factory=list, description="Question types")
    difficulty: str = Field("medium", description="Difficulty")
    count: int = Field(10, ge=1, le=100, description="Question count")


class QuestionGenerateResponse(BaseModel):
    questions: List[QuestionItem]

