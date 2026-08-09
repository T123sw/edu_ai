from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.chat.domain.artifact_reference import ArtifactReferencePayload
from app.chat.domain.contracts import ChatInputImagePayload, ChatInputVideoPayload
from app.chat.domain.conversation_reference import ConversationReferencePayload
from app.chat.domain.status_card import StatusCardViewModel
from app.services.generation_source_resolver import GenerationSourceMode

TracePath = Literal["fast", "workflow"]
DirectTracePath = Literal["direct"]
WorkflowStatus = Literal["running", "awaiting_confirm", "completed", "interrupted", "failed"]
ReportEntryMode = Literal["knowledge_base_report", "chat_report"]
PptEntryMode = Literal["knowledge_base_ppt"]
LessonPlanEntryMode = Literal["knowledge_base_lesson_plan"]
QuizEntryMode = Literal["knowledge_base_quiz"]
GameType = Literal["category_sort", "drag_match", "memory_flip"]
ReportEntryCardType = Literal["preset", "recommended"]
PresetKey = Literal["brief", "detailed", "study_plan", "custom"]
PptPresetKey = Literal["knowledge_lecture", "topic_briefing", "comparison_analysis", "defense_summary"]
LessonPlanPresetKey = Literal["new_lesson", "review_lesson", "inquiry_lesson", "practice_lesson"]
RecommendationType = Literal[
    "summary",
    "comparison",
    "risk_analysis",
    "teaching_suggestion",
    "study_focus",
    "theme_outline",
]
PptRecommendationType = Literal["concept_focus", "process_flow", "comparison_view", "case_application"]
LessonPlanRecommendationType = Literal[
    "knowledge_building",
    "historical_inquiry",
    "practice_consolidation",
    "review_summary",
    "material_analysis",
]
FitScore = Literal["high", "medium", "low"]
PptLengthOption = Literal["short", "medium", "long"]
PptThemeId = Literal["heu_academic_elegant", "heu_academic_basic"]
QuizDifficulty = Literal["easy", "medium", "hard"]
QuizQuestionType = Literal["choice", "blank", "short", "judge"]
GenerationPreflightResourceType = Literal[
    "report",
    "lesson_plan",
    "blog",
    "quiz",
    "ppt",
    "flashcard",
    "graph",
    "game",
    "classroom",
]
GenerationToolIdV2 = Literal[
    "report",
    "ppt",
    "mind_map",
    "quiz",
    "classroom",
    "lesson_plan",
    "blog",
    "flashcard",
    "game",
]


class GenerationToolDefinitionV2(BaseModel):
    tool_id: GenerationToolIdV2
    output_scope: Literal["personal"] = "personal"
    allowed_source_scopes: List[Literal["none", "personal", "course"]]
    can_publish: Literal[False] = False


class GenerationToolCatalogResponseV2(BaseModel):
    tools: List[GenerationToolDefinitionV2]


class GenerationSourceRequest(BaseModel):
    source_mode: GenerationSourceMode = "course_auto"
    selected_doc_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_selected_mode(cls, value):
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


class GenerationPreflightRequestV2(GenerationSourceRequest):
    course_id: str = Field(min_length=1)
    resource_type: GenerationPreflightResourceType


class GenerationPreflightDocumentV2(BaseModel):
    document_id: str
    name: str
    chunk_count: int = Field(ge=0)


class GenerationPreflightResponseV2(BaseModel):
    valid: Literal[True] = True
    source_mode: GenerationSourceMode
    ready_document_count: int = Field(ge=0)
    documents: List[GenerationPreflightDocumentV2] = Field(
        default_factory=list
    )
    warnings: List[str] = Field(default_factory=list)


class ChatReplyRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact_reference: Optional[ArtifactReferencePayload] = None
    conversation_reference: Optional[ConversationReferencePayload] = None
    allow_rag: bool = False
    allow_web: bool = False
    source_mode: Optional[GenerationSourceMode] = None
    selected_doc_ids: List[str] = Field(default_factory=list)
    input_images: List[ChatInputImagePayload] = Field(default_factory=list)
    input_videos: List[ChatInputVideoPayload] = Field(default_factory=list)
    action_hint: Optional[str] = None


class ChatReportRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    selected_doc_ids: List[str] = Field(default_factory=list)
    report_config: Optional[Dict[str, Any]] = None
    entry_mode: Optional[ReportEntryMode] = None
    prompt_draft: Optional[str] = None
    final_user_prompt: Optional[str] = None
    selected_card: Optional["ReportEntryCardSelectionV2"] = None


class ChatReportCardsRequestV2(BaseModel):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)


class ChatPptCardsRequestV2(BaseModel):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)


class ChatLessonPlanCardsRequestV2(BaseModel):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)


class KnowledgeBaseDirectLessonPlanRequestV2(GenerationSourceRequest):
    course_id: str = Field(min_length=1)
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    topic: str = Field(min_length=1, max_length=200)
    audience: str = Field(default="", max_length=200)
    duration_minutes: int = Field(default=45, ge=10, le=480)
    objectives: List[str] = Field(default_factory=list, max_length=12)
    lesson_type: str = Field(default="knowledge_building", max_length=80)
    teaching_process: str = Field(default="", max_length=4000)
    special_requirements: str = Field(default="", max_length=2000)
    include_visuals: bool = True
    outline_preview: bool = True
    deadline_seconds: int = Field(default=300, ge=1, le=3600)
    idempotency_key: Optional[str] = Field(
        default=None, min_length=1, max_length=160
    )


class KnowledgeBaseDirectReportRequestV2(GenerationSourceRequest):
    question: str
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    report_config: Optional[Dict[str, Any]] = None
    prompt_draft: Optional[str] = None
    final_user_prompt: Optional[str] = None
    selected_card: Optional["ReportEntryCardSelectionV2"] = None
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=160)


class KnowledgeBaseDirectQuizPrefillRequestV2(BaseModel):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)


class DirectQuizConfigV2(BaseModel):
    topic: str
    audience: str = Field(default="", max_length=200)
    hard_points: List[str] = Field(default_factory=list)
    difficulty: QuizDifficulty = "medium"
    question_count: int = 5
    question_types: List[QuizQuestionType] = Field(default_factory=lambda: ["choice"])
    include_answers: bool = True
    include_explanations: bool = True


class KnowledgeBaseDirectQuizRequestV2(GenerationSourceRequest):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    quiz_config: DirectQuizConfigV2
    prompt_draft: Optional[str] = None
    final_user_prompt: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=160)


class KnowledgeBaseDirectGameRequestV2(GenerationSourceRequest):
    course_id: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    game_type: GameType
    topic: str = Field(default="", max_length=200)
    card_count: int = Field(default=8, ge=4, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    duration_minutes: int = Field(default=5, ge=1, le=60)
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=160)


class DirectFlashcardConfigV2(BaseModel):
    title: str = ""
    count: int = Field(default=10, ge=3, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    category: str = ""
    show_sources: bool = True


class KnowledgeBaseDirectFlashcardRequestV2(GenerationSourceRequest):
    course_id: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    flashcard_config: DirectFlashcardConfigV2
    idempotency_key: str = Field(min_length=1, max_length=160)


class PptEntryPrefillConfigV2(BaseModel):
    deck_title: str
    deck_subtitle: Optional[str] = None
    audience: str = ""
    objective: str = ""
    theme_id: PptThemeId = "heu_academic_elegant"
    length_option: PptLengthOption = "medium"
    target_slide_count: int = 0
    key_points: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None
    special_requirements: Optional[str] = None
    general_requirements: Optional[str] = None


class KnowledgeBaseDirectPptOutlineRequestV2(GenerationSourceRequest):
    course_id: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    ppt_config: PptEntryPrefillConfigV2


class KnowledgeBaseDirectPptGenerateRequestV2(BaseModel):
    draft_id: str = Field(min_length=1)
    confirm: bool = True
    outline: Optional[Dict[str, Any]] = None
    idempotency_key: str = Field(min_length=1, max_length=160)


class KnowledgeBaseDirectGraphRequestV2(GenerationSourceRequest):
    course_id: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    title: str = ""
    description: str = Field(default="", max_length=2000)
    max_depth: int = Field(default=3, ge=2, le=5)
    idempotency_key: str = Field(min_length=1, max_length=160)


class KnowledgeBaseDirectBlogRequestV2(GenerationSourceRequest):
    course_id: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    topic: str = Field(min_length=1, max_length=160)
    audience: str = Field(default="", max_length=200)
    tone: Literal["academic", "popular", "narrative"] = "popular"
    length: Literal["short", "medium", "long"] = "medium"
    structure: str = Field(default="", max_length=1000)
    special_requirements: str = Field(default="", max_length=2000)
    include_visuals: bool = True
    idempotency_key: str = Field(min_length=1, max_length=160)


class LessonPlanEntryPrefillConfigV2(BaseModel):
    topic: str
    audience: str = ""
    duration: str = ""
    lesson_type: str = ""
    objective: str = ""
    key_points: List[str] = Field(default_factory=list)
    difficult_points: List[str] = Field(default_factory=list)
    after_class_task: str = ""
    style_hint: Optional[str] = None


class PptEntryCardSelectionV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    preset_key: Optional[PptPresetKey] = None
    recommendation_type: Optional[PptRecommendationType] = None


class ReportEntryCardSelectionV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    preset_key: Optional[PresetKey] = None
    recommendation_type: Optional[RecommendationType] = None


class ReportEntryCardV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    title: str
    description: str
    prompt_draft: str
    preset_key: Optional[PresetKey] = None
    recommendation_type: Optional[RecommendationType] = None
    recommendation_source: Optional[Literal["doc_summaries"]] = None
    fit_score: Optional[FitScore] = None


class ChatReportCardsResponseV2(BaseModel):
    entry_mode: ReportEntryMode
    cards: List[ReportEntryCardV2] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)


class PptEntryCardV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    title: str
    description: str
    objective_hint: str
    length_option: PptLengthOption
    prefill_config: PptEntryPrefillConfigV2
    preset_key: Optional[PptPresetKey] = None
    recommendation_type: Optional[PptRecommendationType] = None
    recommendation_source: Optional[Literal["doc_summaries"]] = None
    fit_score: Optional[FitScore] = None
    deck_title_hint: Optional[str] = None
    audience_hint: Optional[str] = None
    key_points_hint: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None


class ChatPptCardsResponseV2(BaseModel):
    entry_mode: PptEntryMode
    cards: List[PptEntryCardV2] = Field(default_factory=list)
    default_selected_card_id: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class LessonPlanEntryCardV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    title: str
    description: str
    prompt_draft: str
    prefill_config: LessonPlanEntryPrefillConfigV2
    preset_key: Optional[LessonPlanPresetKey] = None
    recommendation_type: Optional[LessonPlanRecommendationType] = None
    recommendation_source: Optional[Literal["doc_summaries"]] = None
    fit_score: Optional[FitScore] = None


class ChatLessonPlanCardsResponseV2(BaseModel):
    entry_mode: LessonPlanEntryMode
    cards: List[LessonPlanEntryCardV2] = Field(default_factory=list)
    default_selected_card_id: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class ChatQuizPrefillResponseV2(BaseModel):
    entry_mode: QuizEntryMode
    topic: str = ""
    hard_points: List[str] = Field(default_factory=list)
    trace: Dict[str, Any] = Field(default_factory=dict)


class TraceMetaV2(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: TracePath


class DirectTraceMetaV2(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: DirectTracePath


class ChatResponseV2(BaseModel):
    message: Dict[str, Any]
    conversation: Dict[str, Any]
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    trace: TraceMetaV2
    status_card: Optional[StatusCardViewModel] = None


class ChatErrorResponseV2(BaseModel):
    error: Dict[str, Any]
    conversation: Dict[str, Any]
    trace: TraceMetaV2


class ChatDirectReportResponseV2(BaseModel):
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2


class ChatDirectQuizResponseV2(BaseModel):
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2


class ChatDirectGameResponseV2(BaseModel):
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2


class ChatDirectTaskSubmittedResponseV2(BaseModel):
    task_id: str
    status: Literal["pending"] = "pending"
    workflow_type: str
