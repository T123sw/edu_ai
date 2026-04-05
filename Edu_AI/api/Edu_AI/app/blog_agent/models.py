from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BlogGenerateStartRequest(BaseModel):
    course_id: str = Field(..., description="课程ID")
    topic: str = Field(..., description="博客主题")
    selected_doc_ids: Optional[List[str]] = Field(
        default=None, description="可选：限定检索的文档ID列表（后续接入RAG用）"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="检索文档数量（后续接入RAG用）")


class BlogGenerateStartResponse(BaseModel):
    thread_id: str


class BlogTaskProgress(BaseModel):
    current_section_idx: int = 0
    total_sections: int = 0
    current_point_idx: int = 0
    total_points_in_section: int = 0
    total_points_completed: int = 0
    total_points: int = 0


class BlogTaskStatusResponse(BaseModel):
    thread_id: str
    status: str
    progress: BlogTaskProgress
    outline: Optional[List[Dict[str, Any]]] = None
    final_markdown: Optional[str] = None
    error_message: Optional[str] = None


class BlogResumeChaptersRequest(BaseModel):
    """恢复任务（章节审查）请求：用户提交修改后的一级目录（章节列表）"""

    chapters: List[Dict[str, Any]] = Field(..., description="修改后的章节列表")


class BlogResumeOutlineRequest(BaseModel):
    """恢复任务（大纲审查）请求：用户提交修改后的二级目录（含 children）"""

    outline: List[Dict[str, Any]] = Field(..., description="修改后的博客大纲（含小标题 children）")


class BlogTaskState(BaseModel):
    thread_id: str
    course_id: str
    topic: str
    created_at: str
    updated_at: str

    status: str
    progress: BlogTaskProgress = Field(default_factory=BlogTaskProgress)

    outline: List[Dict[str, Any]] = Field(default_factory=list)
    drafts: Dict[str, str] = Field(default_factory=dict)
    final_markdown: Optional[str] = None

    knowledge_graph_match: Dict[str, Any] = Field(default_factory=dict)

    # HITL: 教师对章节（一级目录）的修改意见
    pending_chapters: Optional[List[Dict[str, Any]]] = None

    # HITL: 教师对大纲（二级目录：章节+小标题）的修改意见
    pending_outline: Optional[List[Dict[str, Any]]] = None

    error_message: Optional[str] = None

