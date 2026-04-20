export type BackendCourse = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  objectives?: string[];
  knowledgeGraph?: string;
};

export type CourseMaterial = {
  material_id: string;
  material_type: string;
  title?: string;
  topic?: string;
  summary?: string;
  final_markdown?: string;
  content?: string;
  mainContent?: Array<{ title?: string; content?: string }>;
  outline?: Array<{
    title?: string;
    children?: Array<{ title?: string; key_concepts?: string[] }>;
  }>;
  is_pinned?: boolean;
};

export type KnowledgeBaseDocument = {
  id: string;
  name: string;
  type: "file" | "web";
  file_path?: string | null;
  url?: string | null;
  course_id: string;
  scope_type?: "course" | "knowledge_point";
  scope_id?: string | null;
  library_type?: "course" | "personal";
  owner_user_id?: string | null;
  promoted_from_document_id?: string | null;
  created_at: string;
  updated_at?: string | null;
};

export type KnowledgeBaseScopeOptions = {
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  aggregate?: boolean;
  libraryType?: "course" | "personal";
  includeDescendants?: boolean;
  limit?: number;
  offset?: number;
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

export type KnowledgeGraphHourAllocationRequest = {
  total_hours: number;
};

export type KnowledgeGraphHourAllocationResponse = KnowledgeGraphData & {
  allocation: {
    total_hours?: number;
    leaf_count?: number;
    source?: string;
    normalized?: boolean;
    [key: string]: unknown;
  };
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

export type AiLectureSessionSnapshotEvent = {
  type: string;
  text?: string;
  page_index?: number;
  sentence_index?: number;
  created_at?: string;
  [key: string]: unknown;
};

export type AiLectureSessionSnapshot = {
  snapshot_id: string;
  course_id?: string;
  source_ppt_material_id?: string;
  ai_lecturer_course_id?: string | null;
  outline?: Array<Record<string, unknown>>;
  script?: Array<Record<string, unknown>>;
  events?: AiLectureSessionSnapshotEvent[];
  last_position?: {
    page_index: number;
    sentence_index: number;
  };
  created_at?: string;
  updated_at?: string;
};

export type AiLectureSessionMaterial = CourseMaterial & {
  material_id: string;
  material_type: "ai_lecture_session";
  content?: {
    source_ppt_material_id?: string;
    session_snapshot_id?: string;
    recording_asset_id?: string | null;
    recording_url?: string | null;
    can_continue_interactive?: boolean;
    [key: string]: unknown;
  };
  generation_state?: {
    status?: "created" | "recording" | "completed" | "failed" | string;
    phase?: string;
    message?: string;
    [key: string]: unknown;
  };
};

export type AiLectureSessionDetail = {
  material: AiLectureSessionMaterial;
  snapshot: AiLectureSessionSnapshot;
  metadata: {
    session_id?: string;
    source_ppt_material_id?: string;
    recording_status?: "not_started" | "recording" | "completed" | "failed" | string;
    recording_url?: string | null;
    livetalking_session_id?: number;
    created_at?: string;
    updated_at?: string;
    [key: string]: unknown;
  };
};

export type AiLecturerCoursePage = {
  title: string;
  content: string;
};

export type AiLecturerCourse = {
  course_id: string;
  pages: AiLecturerCoursePage[];
};

export type AiLecturerCourseDetail = {
  course_name: string;
  outline: AiLecturerCoursePage[];
};

export type AiLecturerScriptResult = {
  sentences: string[];
};

export type AiLecturerAskResult = {
  answer: string;
};

export type AiLecturerOfferAnswer = {
  sdp: string;
  type: RTCSdpType;
  sessionid: number;
};

export type AiLecturerOfflineTaskCreated = {
  task_id: string;
};

export type AiLecturerOfflineTaskStatus = {
  status: "processing" | "success" | "failed";
  video_url?: string;
  error?: string;
};
