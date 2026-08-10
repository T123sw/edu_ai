export type BackendCourse = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  objectives?: string[];
  audience?: string | null;
  language?: string | null;
  difficulty?: string | null;
  knowledgeGraph?: string;
  revision: number;
  membership_role: "owner" | "editor" | "viewer";
  course_code?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CourseMember = {
  course_id: string;
  user_id: string;
  username: string;
  system_role: "admin" | "teacher" | "student" | string;
  role: "owner" | "editor" | "viewer";
  joined_at: string;
  added_by: string;
};

export type BackendCourseCreatePayload = {
  id?: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  objectives: string[];
  audience: string;
  language: string;
  difficulty: string;
  knowledgeGraph?: string;
};

export type CourseMaterialVisibility = "private" | "course";
export type CourseMaterialSpace = "mine" | "course";
export type PublicationAction = "published" | "updated" | "unchanged";

export type LearningResourceRef = {
  material_type: string;
  material_id: string;
};

export type TaskProgress = {
  task_id: string;
  course_id: string;
  student_id: string;
  status: "not_started" | "in_progress" | "completed";
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
};

export type LearningTask = {
  task_id: string;
  course_id: string;
  title: string;
  instructions: string;
  created_by: string;
  resource_refs: LearningResourceRef[];
  knowledge_point_ids: string[];
  status: "draft" | "published" | "closed";
  created_at: string;
  published_at: string | null;
  published_by: string | null;
  my_progress: TaskProgress | null;
};

export type CourseLearningSummary = {
  task: LearningTask;
  enrolled_students: number;
  started_students: number;
  completed_students: number;
  completion_rate: number;
  progress: TaskProgress[];
};

export type LearningTaskCreatePayload = {
  title: string;
  instructions: string;
  resource_refs: LearningResourceRef[];
  knowledge_point_ids: string[];
};

export type LearningEventPayload = {
  event_id: string;
  event_type: "started" | "resource_opened" | "progress_updated" | "completed";
  progress_percent: number;
  resource_ref?: LearningResourceRef | null;
};

export type LearningEventResponse = {
  created: boolean;
  progress: TaskProgress;
};

export type CourseMaterial = {
  schema_version?: number;
  version?: number;
  material_id: string;
  material_type: string;
  course_id?: string;
  owner_user_id?: string | null;
  created_by?: string | null;
  visibility?: CourseMaterialVisibility;
  source_job_id?: string | null;
  config_snapshot_id?: string | null;
  source?: Record<string, unknown>;
  source_snapshot?: Record<string, unknown>;
  content_hash?: string;
  artifact_paths?: string[];
  published_material_id?: string | null;
  published_version?: number | null;
  published_at?: string | null;
  published_by?: string | null;
  published_from_material_id?: string | null;
  published_from_owner_user_id?: string | null;
  published_from_version?: number | null;
  publication_status?: "published" | null;
  title?: string;
  topic?: string;
  summary?: string;
  final_markdown?: string;
  markdown?: string;
  report?: unknown;
  report_content?: string;
  text?: string;
  content?: unknown;
  mainContent?: Array<{ title?: string; content?: string }>;
  outline?: Array<{
    title?: string;
    children?: Array<{ title?: string; key_concepts?: string[] }>;
  }>;
  questions?: Array<{
    id?: string;
    type?: string;
    stem?: string;
    options?: string[] | null;
    answer?: string;
    explanation?: string;
  }>;
  plan?: {
    title?: string;
    objectives?: string[];
    keyPoints?: string[];
    hardPoints?: string[];
    process?: Array<{ step?: string; content?: string; duration?: string }>;
    homework?: string;
  };
  is_pinned?: boolean;
  pinned_at?: string | null;
  created_at?: string;
  updated_at?: string;
  status?: string;
  stage?: { id?: string; name?: string; [key: string]: unknown };
  scenes?: ClassroomScene[];
  scenes_count?: number;
  source_count?: number;
  voice_status?: string;
  video_url?: string;
  video_status?: string;
  pptx_url?: string;
  html_url?: string;
  flashcards?: Array<{
    front?: string;
    back?: string;
    category?: string;
    source?: string;
  }>;
  scope_type?: "course" | "knowledge_point";
  scope_id?: string | null;
};

export type MaterialPublicationResponse = {
  action: PublicationAction;
  source_material_id: string;
  material: CourseMaterial;
};

export type KnowledgeBaseDocument = {
  id: string;
  name: string;
  display_name?: string | null;
  type: "file" | "web";
  file_path?: string | null;
  url?: string | null;
  source_title?: string | null;
  source_domain?: string | null;
  source_site_name?: string | null;
  source_icon_url?: string | null;
  source_license?: string | null;
  source_license_url?: string | null;
  source_revision?: string | null;
  source_language?: string | null;
  content_language?: string | null;
  translation_notice?: string | null;
  usage_restriction?: string | null;
  authority_tier?: string | null;
  retrieved_at?: string | null;
  course_id: string;
  scope_type?: "course" | "knowledge_point";
  scope_id?: string | null;
  library_type?: "course" | "personal";
  owner_user_id?: string | null;
  promoted_from_document_id?: string | null;
  created_at: string;
  updated_at?: string | null;
  status: "received" | "parsing" | "chunking" | "embedding" | "indexing" | "ready" | "partially_ready" | "failed";
  active_index_version?: string | null;
  pending_index_version?: string | null;
  page_count: number;
  chunk_count: number;
  failed_units: number;
  indexed_at?: string | null;
  last_job_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
};

export type KnowledgeBaseScopeOptions = {
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  aggregate?: boolean;
  libraryType?: "course" | "personal";
  includeDescendants?: boolean;
  limit?: number;
  offset?: number;
  sort?: "created_desc" | "created_asc" | "name_asc" | "name_desc";
};

export type CourseKnowledgeTopic = {
  topic_id: string;
  title: string;
  query: string;
  objective: string;
};

export type CourseKnowledgeSourceCandidate = {
  candidate_id: string;
  topic_id: string;
  title: string;
  url: string;
  domain: string;
  source_type: string;
  language?: string | null;
  license_name?: string | null;
  license_url?: string | null;
  authority_tier: string;
  review_status: "approved" | "rejected" | "pending";
  review_reason: string;
  selected: boolean;
  relevance_score: number;
  metadata?: Record<string, unknown>;
};

export type CourseKnowledgeQualityCheck = {
  check_type: string;
  status: "passed" | "failed";
  score?: number | null;
  threshold?: number | null;
  details: Record<string, unknown>;
};

export type CourseKnowledgeBuild = {
  build_id: string;
  library_id?: string;
  course_id: string;
  status: "draft" | "queued" | "running" | "publishing" | "succeeded" | "failed" | "blocked" | "canceled";
  phase: string;
  progress?: number;
  course_snapshot: Record<string, unknown>;
  topics: CourseKnowledgeTopic[];
  source_candidates: CourseKnowledgeSourceCandidate[];
  warnings: string[];
  metrics?: Record<string, unknown>;
  quality_score?: number | null;
  quality_checks?: CourseKnowledgeQualityCheck[];
  error?: { code?: string; message?: string } | null;
};

export type CourseKnowledgeGraphVersion = {
  version: number;
  source_build_id?: string | null;
  created_at: string;
  published_at?: string | null;
  node_count: number;
};

export type KnowledgeBaseDocumentContent = {
  document_id: string;
  file_path: string;
  file_name: string;
  content: string;
  chunks: Array<{
    id: number;
    content: string;
    page: number;
    metadata: Record<string, unknown>;
  }>;
  total_chunks: number;
};

export type KnowledgeGraphNode = {
  id: string;
  label: string;
  children?: KnowledgeGraphNode[];
  data?: {
    level?: number;
    summary?: string;
    hasChildren?: boolean;
    type?: string;
    hours?: number;
  };
};

export type KnowledgeGraphData = {
  root: KnowledgeGraphNode;
};

export type KnowledgeGraphSplitDocument = {
  id: string;
  title: string;
  section_titles: string[];
  file_path: string;
  char_count: number;
  preview: string;
};

export type KnowledgeGraphVectorizedDocument = {
  title: string;
  file_path: string;
  status: string;
  message: string;
  chunk_count: number;
};

export type KnowledgeGraphTextbookImportResponse = {
  source_document: KnowledgeBaseDocument;
  parser_used: string;
  outline_source: string;
  llm_env_path: string;
  graph_material_id: string;
  parsed_markdown_path: string;
  knowledge_graph: KnowledgeGraphData;
  split_documents: KnowledgeGraphSplitDocument[];
  vectorized_documents: KnowledgeGraphVectorizedDocument[];
  warnings: string[];
};

export type ChatReplyRequestV2 = {
  question: string;
  conversation_id?: string | null;
  course_id?: string | null;
  allow_rag?: boolean;
  allow_web?: boolean;
  selected_doc_ids?: string[];
  action_hint?: string | null;
};

export type ChatResponseV2 = {
  message?: {
    role?: string;
    content?: string;
  };
  conversation?: {
    conversation_id?: string;
  };
  artifacts?: Array<Record<string, unknown>>;
  action?: Record<string, unknown>;
  answer?: string;
};

export type ChatCardsRequestV2 = {
  course_id?: string | null;
  selected_doc_ids?: string[];
};

export type PptEntryCard = {
  card_id: string;
  card_type: string;
  title: string;
  description: string;
  objective_hint: string;
  length_option: "short" | "medium" | "long";
  preset_key?: string | null;
  recommendation_type?: string | null;
  deck_title_hint?: string | null;
  audience_hint?: string | null;
  key_points_hint?: string[];
  style_hint?: string | null;
};

export type ChatPptCardsResponse = {
  entry_mode?: string;
  cards: PptEntryCard[];
  trace?: Record<string, unknown>;
};

export type ChatDirectPptOutlineRequest = {
  course_id?: string | null;
  selected_doc_ids?: string[];
  ppt_config: {
    deck_title: string;
    deck_subtitle?: string;
    audience: string;
    objective: string;
    theme_id: string;
    length_option: "short" | "medium" | "long";
    target_slide_count?: number;
    key_points?: string[];
    style_hint?: string;
    special_requirements?: string;
    general_requirements?: string;
    selected_card?: {
      card_id: string;
      card_type: string;
      preset_key?: string | null;
      recommendation_type?: string | null;
    };
  };
};

export type ChatDirectPptOutlineResponse = {
  action?: Record<string, unknown>;
  draft?: {
    draft_id?: string;
    status?: string;
    outline?: Record<string, unknown>;
    normalized_ppt_config?: Record<string, unknown>;
    [key: string]: unknown;
  };
  artifacts?: Array<Record<string, unknown>>;
  trace?: Record<string, unknown>;
};

export type ChatDirectPptGenerateRequest = {
  draft_id: string;
  confirm: boolean;
  outline?: Record<string, unknown> | null;
};

export type ChatDirectPptGenerateResponse = {
  action?: Record<string, unknown>;
  run?: Record<string, unknown>;
  artifacts?: Array<Record<string, unknown>>;
  trace?: Record<string, unknown>;
};

export type LessonPlanResponse = {
  id?: string | null;
  title: string;
  objectives: string[];
  keyPoints: string[];
  hardPoints: string[];
  process: Array<{ step: string; content: string; duration: string }>;
  homework: string;
};

export type ReportResponse = {
  id?: string | null;
  title: string;
  summary: string;
  introduction: string;
  mainContent: Array<{
    title: string;
    content: string;
    subsections?: Array<{ title: string; content: string }>;
  }>;
  keyFindings: string[];
  conclusions: string;
  recommendations?: string[];
};

export type QuizResponse = {
  id?: string | null;
  title: string;
  difficulty: string;
  question_type: string;
  questions: Array<{
    id: string;
    type: string;
    stem: string;
    options?: string[];
    answer: string;
    explanation: string;
  }>;
};

export type KnowledgePointsResponse = {
  knowledge_points: string[];
};

export type QuestionGenerateResponse = {
  questions: Array<{
    id: number;
    type: string;
    difficulty: string;
    content: string;
    options?: string[];
    answer?: string | null;
    analysis?: string | null;
  }>;
};

export type VideoSearchHit = {
  id: string;
  score?: number;
  transcript: string;
  course_id?: string | null;
  source_original_path?: string | null;
  source_chunk_path?: string | null;
  start_time?: number | null;
  end_time?: number | null;
  playback_url?: string | null;
  stream_url?: string | null;
};

export type VideoSearchResponse = {
  query: string;
  hits: VideoSearchHit[];
};

export type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

export type { JobRecord as EduJob } from "../../jobs/types";

export type ClassroomQuizQuestion = {
  id: string;
  type: "single" | "multiple" | "short_answer" | string;
  question: string;
  options?: Array<{ value: string; label: string }>;
  answer?: string[];
  analysis?: string;
  commentPrompt?: string;
  points?: number;
  hasAnswer?: boolean;
};

export type SlideClassroomContent = {
  type: "slide";
  canvas: Record<string, unknown>;
};

export type InteractiveClassroomContent = {
  type: "interactive";
  url?: string;
  html?: string;
  widgetType?: string;
  widgetConfig?: Record<string, unknown>;
};

export type QuizClassroomContent = {
  type: "quiz";
  questions: ClassroomQuizQuestion[];
};

export type UnknownClassroomContent = {
  type?: string;
  [key: string]: unknown;
};

export type ClassroomSceneContent =
  | SlideClassroomContent
  | InteractiveClassroomContent
  | QuizClassroomContent
  | UnknownClassroomContent;

export type ClassroomScene = {
  id: string;
  type: string;
  title?: string;
  order?: number;
  content?: ClassroomSceneContent;
  actions?: Array<Record<string, unknown>>;
};

export type ClassroomMaterial = {
  material_id: string;
  material_type: string;
  title?: string;
  owner?: string | null;
  stage?: { id: string; name?: string; [key: string]: unknown };
  scenes?: ClassroomScene[];
  scenes_count?: number;
  voice_status?: string;
  sidecar_url?: string;
  sidecar_created_at?: string;
  course_id?: string;
  created_at?: string;
  updated_at?: string;
};

export type ClassroomQaCheckpoint = {
  scene_id: string;
  scene_index: number;
  action_index: number;
  action_id: string | null;
  phase: "executing_action" | "between_actions";
  page_revision: number;
};

export type ClassroomQaTurnRequest = {
  client_turn_id: string;
  question: string;
  checkpoint: ClassroomQaCheckpoint;
};

export type ClassroomQaTurn = {
  turn_id: string;
  client_turn_id: string;
  question: string;
  answer_text: string;
  transition_text: string;
  tts_status: "ready" | "failed";
  audio_url: string | null;
  created_at: string;
};

export type ClassroomQaSession = {
  session_id: string;
  course_id: string;
  classroom_id: string;
  owner_user_id: string;
  status: "ready";
  turns: ClassroomQaTurn[];
};

export type ClassroomQaTurnSubmission = {
  session_id: string;
  turn: ClassroomQaTurn;
};
