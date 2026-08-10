"""Pydantic models for course management — no HTTP or business dependencies."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.workspace_scope import SCOPE_TYPE_COURSE
from core.course_storage import LIBRARY_TYPE_COURSE, LIBRARY_TYPE_PERSONAL
from app.services.generation_source_resolver import GenerationSourceMode


class CourseInfo(BaseModel):
    id: str = Field(..., description="课程 ID")
    title: str = Field(..., description="课程名称")
    description: str = Field(..., description="课程描述")
    icon: str = Field(..., description="前端图标名")
    color: str = Field(..., description="主题色")
    objectives: Optional[List[str]] = Field(default=None, description="教学目标")
    audience: Optional[str] = Field(default=None, description="教学对象或年级")
    language: Optional[str] = Field(default=None, description="授课语言")
    difficulty: Optional[str] = Field(default=None, description="课程难度")
    knowledgeGraph: Optional[str] = Field(default=None, description="知识图谱")
    revision: int = 0
    membership_role: Optional[Literal["owner", "editor", "viewer"]] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CourseCreateRequest(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    title: str = Field(..., min_length=1)
    description: str
    icon: str
    color: str
    objectives: Optional[List[str]] = None
    audience: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=50)
    difficulty: Optional[str] = Field(default=None, max_length=50)
    knowledgeGraph: Optional[str] = None

    @field_validator("id")
    @classmethod
    def validate_course_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized in {".", ".."} or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in normalized
        ):
            raise ValueError("课程 ID 只能包含字母、数字、点、下划线和连字符")
        return normalized


class CourseUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str
    icon: str
    color: str
    objectives: Optional[List[str]] = None
    audience: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=50)
    difficulty: Optional[str] = Field(default=None, max_length=50)
    knowledgeGraph: Optional[str] = None
    expected_revision: int = Field(..., ge=0)


class KnowledgeBaseDocument(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    type: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    source_title: Optional[str] = None
    source_domain: Optional[str] = None
    source_site_name: Optional[str] = None
    source_icon_url: Optional[str] = None
    source_license: Optional[str] = None
    source_license_url: Optional[str] = None
    source_revision: Optional[str] = None
    source_language: Optional[str] = None
    content_language: Optional[str] = None
    translation_notice: Optional[str] = None
    usage_restriction: Optional[str] = None
    authority_tier: Optional[str] = None
    retrieved_at: Optional[str] = None
    course_id: str
    scope_type: str = SCOPE_TYPE_COURSE
    scope_id: Optional[str] = None
    library_type: str = LIBRARY_TYPE_COURSE
    owner_user_id: Optional[str] = None
    promoted_from_document_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    status: str = "received"
    active_index_version: Optional[str] = None
    pending_index_version: Optional[str] = None
    page_count: int = 0
    chunk_count: int = 0
    failed_units: int = 0
    parser_name: Optional[str] = None
    embedding_profile_id: Optional[str] = None
    indexed_at: Optional[str] = None
    last_job_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class KnowledgeBaseDocumentContentChunk(BaseModel):
    id: int
    content: str
    page: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseDocumentContent(BaseModel):
    document_id: str
    file_path: str
    file_name: str
    content: str
    chunks: List[KnowledgeBaseDocumentContentChunk] = Field(default_factory=list)
    total_chunks: int = 0


class KnowledgeBaseDocumentUploadResponse(BaseModel):
    document: KnowledgeBaseDocument
    job: Dict[str, Any]


class KnowledgeBaseRetrievalTestRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeBaseRetrievalHit(BaseModel):
    chunk_id: str
    content: str
    score: float
    page: Optional[int] = None
    timestamp: Optional[str] = None
    reranked: bool = False


class KnowledgeBaseRetrievalTestResponse(BaseModel):
    document_id: str
    index_version: str
    query: str
    hits: List[KnowledgeBaseRetrievalHit] = Field(default_factory=list)
    elapsed_ms: int


class CourseKnowledgeBuildRequest(BaseModel):
    source_id: str = Field(default="auto", min_length=1, max_length=100)
    max_pages: int = Field(default=160, ge=1, le=200)
    clean_placeholders: bool = True


class CourseKnowledgeBuildPreviewRequest(BaseModel):
    discover_sources: bool = True
    max_results_per_topic: int = Field(default=6, ge=1, le=12)


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

class RenameMaterialRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class MaterialContentUpdateRequest(BaseModel):
    content: Any


class MaterialPublicationResponse(BaseModel):
    action: Literal["published", "updated", "unchanged"]
    source_material_id: str
    material: Dict[str, Any]


class GenerateClassroomRequest(BaseModel):
    topic: Optional[str] = Field(default=None, max_length=200)
    audience: str = Field(default="", max_length=200)
    objectives: List[str] = Field(default_factory=list, max_length=12)
    scene_count: int = Field(default=6, ge=1, le=30)
    duration_minutes: int = Field(default=25, ge=5, le=180)
    teaching_style: Literal["guided", "lecture", "inquiry"] = "guided"
    source_mode: GenerationSourceMode = "course_auto"
    selected_doc_ids: List[str] = Field(default_factory=list)
    """SPEC-04 §1 GenerateClassroomInput 的 edu_ai 子集（图片/视频生成 flags 仍不开放，见 §0.1 D2）。"""

    requirement: str = Field(..., description="课件需求文本")
    enable_web_search: bool = Field(
        default=False, description="是否启用 sidecar 内建 web search（edu_ai 默认走 SPEC-00 独立检索层，这里通常不开）"
    )
    enable_tts: bool = Field(
        default=True,
        description="是否生成真人配音（D1，SPEC-04 §5）。sidecar 未配置 TTS provider 时会静默跳过，自动退回前端浏览器 TTS/静音等待兜底",
    )
    voice: Literal["", "alloy", "nova", "shimmer"] = "alloy"
    include_visuals: bool = True
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=160)


    @model_validator(mode="before")
    @classmethod
    def infer_legacy_source_mode(cls, value):
        if isinstance(value, dict) and "source_mode" not in value:
            value = dict(value)
            if value.get("selected_doc_ids"):
                value["source_mode"] = "selected_documents"
        return value

    @model_validator(mode="after")
    def validate_source_selection(self) -> Self:
        self.selected_doc_ids = list(
            dict.fromkeys(
                str(item or "").strip()
                for item in self.selected_doc_ids
                if str(item or "").strip()
            )
        )
        if self.source_mode == "selected_documents" and not self.selected_doc_ids:
            raise ValueError("selected_documents requires at least one document")
        if self.source_mode != "selected_documents" and self.selected_doc_ids:
            raise ValueError(
                "selected_doc_ids is only valid for selected_documents"
            )
        return self


class KnowledgeGraphData(BaseModel):
    root: dict = Field(..., description="知识图谱根节点")


class KnowledgeGraphHourAllocationRequest(BaseModel):
    total_hours: float = Field(..., description="Course total hours, with at most one decimal place")


class KnowledgeGraphHourAllocationResponse(KnowledgeGraphData):
    allocation: Dict[str, Any] = Field(default_factory=dict, description="Hour allocation metadata")

