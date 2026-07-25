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


class GenerateClassroomRequest(BaseModel):
    """SPEC-04 §1 GenerateClassroomInput 的 edu_ai 子集（图片/视频生成 flags 仍不开放，见 §0.1 D2）。"""

    requirement: str = Field(..., description="课件需求文本")
    enable_web_search: bool = Field(
        default=False, description="是否启用 sidecar 内建 web search（edu_ai 默认走 SPEC-00 独立检索层，这里通常不开）"
    )
    enable_tts: bool = Field(
        default=True,
        description="是否生成真人配音（D1，SPEC-04 §5）。sidecar 未配置 TTS provider 时会静默跳过，自动退回前端浏览器 TTS/静音等待兜底",
    )


class KnowledgeGraphData(BaseModel):
    root: dict = Field(..., description="知识图谱根节点")


class KnowledgeGraphHourAllocationRequest(BaseModel):
    total_hours: float = Field(..., description="Course total hours, with at most one decimal place")


class KnowledgeGraphHourAllocationResponse(KnowledgeGraphData):
    allocation: Dict[str, Any] = Field(default_factory=dict, description="Hour allocation metadata")

