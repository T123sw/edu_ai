from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title")
    course_id: Optional[str] = Field(None, description="Course ID")
    selected_doc_ids: List[str] = Field(..., description="Selected document ids")
    focus_areas: Optional[List[str]] = Field(None, description="Focus areas")


class ReportSection(BaseModel):
    title: str
    content: str
    subsections: Optional[List[Dict[str, str]]] = None


class ReportResponse(BaseModel):
    id: Optional[str] = None
    title: str
    summary: str
    introduction: str
    mainContent: List[ReportSection]
    keyFindings: List[str]
    conclusions: str
    recommendations: Optional[List[str]] = None

