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
  created_at: string;
  updated_at?: string | null;
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

export type AiLecturerOfflineTaskCreated = {
  task_id: string;
};

export type AiLecturerOfflineTaskStatus = {
  status: "processing" | "success" | "failed";
  video_url?: string;
  error?: string;
};
