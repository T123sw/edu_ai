from typing import List, Optional

from pydantic import BaseModel, Field


class QuizRequest(BaseModel):
    title: Optional[str] = Field(None, description="Quiz title")
    course_id: Optional[str] = Field(None, description="Course ID")
    selected_doc_ids: List[str] = Field(..., description="Selected document ids")
    question_type: str = Field("mixed", description="Question type")
    count: int = Field(10, ge=5, le=20, description="Question count")
    difficulty: str = Field("medium", description="Difficulty")


class QuizQuestion(BaseModel):
    id: str
    type: str
    stem: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str


class QuizResponse(BaseModel):
    id: Optional[str] = None
    title: str
    difficulty: str
    question_type: str
    questions: List[QuizQuestion]

