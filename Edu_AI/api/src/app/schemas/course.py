"""Pydantic models for course management — no HTTP or business dependencies."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.workspace_scope import SCOPE_TYPE_COURSE
from core.course_storage import LIBRARY_TYPE_COURSE, LIBRARY_TYPE_PERSONAL


class CourseInfo(BaseModel):
    id: str = Field(..., description="课程 ID")
    title: str = Field(..., description="课程名称")
    description: str = Field(..., description="课程描述")
    icon: str = Field(..., description="前端图标名")
    color: str = Field(..., description="主题色")
    objectives: Optional[List[str]] = Field(default=None, description="教学目标")
    knowledgeGraph: Optional[str] = Field(default=None, description="知识图谱")


class KnowledgeBaseDocument(BaseModel):
    id: str
    name: str
    type: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    course_id: str
    scope_type: str = SCOPE_TYPE_COURSE
    scope_id: Optional[str] = None
    library_type: str = LIBRARY_TYPE_COURSE
    owner_user_id: Optional[str] = None
    promoted_from_document_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class AddRAGDocumentRequest(BaseModel):
    rag_file_path: str = Field(..., description="RAG document identifier")
    scope_type: str = Field(default=SCOPE_TYPE_COURSE, description="workspace scope type")
    scope_id: Optional[str] = Field(default=None, description="workspace scope identifier")
    library_type: str = Field(default=LIBRARY_TYPE_COURSE, description="target library type")
    promoted_from_document_id: Optional[str] = Field(
        default=None, description="source personal document id when promoting into course knowledge base"
    )


class PinMaterialRequest(BaseModel):
    is_pinned: bool = Field(..., description="是否置顶")


class KnowledgeGraphData(BaseModel):
    root: dict = Field(..., description="知识图谱根节点")


class KnowledgeGraphHourAllocationRequest(BaseModel):
    total_hours: float = Field(..., description="Course total hours, with at most one decimal place")


class KnowledgeGraphHourAllocationResponse(KnowledgeGraphData):
    allocation: Dict[str, Any] = Field(default_factory=dict, description="Hour allocation metadata")


class TeachingVideoPptItem(BaseModel):
    material_id: str
    title: str
    pptx_url: str
    html_full_url: Optional[str] = None
    slide_count: Optional[int] = None
    updated_at: Optional[str] = None


class CreateTeachingVideoTaskRequest(BaseModel):
    ppt_material_id: str = Field(..., description="课程 PPT 资源 ID")


class TeachingVideoTaskResponse(BaseModel):
    task_id: str
    material_id: Optional[str] = None
    status: str
    video_url: Optional[str] = None
