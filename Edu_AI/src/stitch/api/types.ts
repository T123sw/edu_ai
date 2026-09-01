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
  snapshot_id?: string | null;
};

export type LearningTaskResourceSnapshot = {
  snapshot_id: string;
  task_id: string;
  position: number;
  source_material_type: string;
  source_material_id: string;
  source_version: number;
  origin_type: "personal" | "standard" | "legacy_shared";
  standard_kind?: StandardResourceKind | null;
  title: string;
  content_payload: Record<string, unknown>;
  file_refs: string[];
  created_at: string;
};

export type CompletionBasis =
  | "none"
  | "self_reported"
  | "activity_evidenced"
  | "assessment_verified";

export type TaskProgress = {
  task_id: string;
  course_id: string;
  student_id: string;
  status: "not_started" | "in_progress" | "completed";
  progress_percent: number;
  completion_basis?: CompletionBasis | null;
  evidence_count: number;
  last_activity_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
};

export type TaskResourceEvidence = {
  resource_id: string;
  resource_version: number;
  condition_status: "pending" | "satisfied";
  evidence_source: "course_resource_learning";
  resource_completed_at: string | null;
};

export type LearningOverview = {
  course_id: string;
  pending_tasks: number;
  in_progress_tasks: number;
  self_reported_completed_tasks: number;
  activity_evidenced_completed_tasks: number;
  assessment_verified_completed_tasks: number;
  latest_activity_at: string | null;
  enrolled_students?: number | null;
};

export type LearningTask = {
  task_id: string;
  course_id: string;
  title: string;
  instructions: string;
  created_by: string;
  task_type: "reading" | "assessed";
  resource_refs: LearningResourceRef[];
  resource_snapshots: LearningTaskResourceSnapshot[];
  knowledge_point_ids: string[];
  status: "draft" | "published" | "closed";
  created_at: string;
  published_at: string | null;
  published_by: string | null;
  my_progress: TaskProgress | null;
  resource_evidence?: TaskResourceEvidence[];
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
  task_type: "reading" | "assessed";
  title: string;
  instructions: string;
  resource_refs: LearningResourceRef[];
  knowledge_point_ids: string[];
};

export type AssessmentQualityIssue = {
  code: string;
  assessment_item_id: string | null;
  message: string;
};

export type AssessmentItemDraft = {
  assessment_item_id: string;
  assessment_version_id: string;
  position: number;
  item_type: string;
  prompt: Record<string, unknown>;
  scoring_key: Record<string, unknown>;
  rubric: Record<string, unknown>;
  max_score: number;
  grading_provider: string;
  knowledge_point_ids: string[];
  source_refs: Array<Record<string, unknown>>;
  source_exposure_state: string;
  created_origin: string;
};

export type AssessmentDraft = {
  assessment_version_id: string;
  assessment_id: string;
  task_id: string;
  course_id: string;
  version_number: number;
  status: "draft" | "published";
  source_mode: string;
  assessment_mode: "closed_book" | "open_book";
  pass_threshold: number;
  mastery_threshold: number;
  max_attempts: number;
  score_policy: string;
  answer_reveal_policy: string;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  draft_revision: number;
  content_hash: string | null;
  published_at: string | null;
  published_by: string | null;
  created_at: string;
  items: AssessmentItemDraft[];
  quality: { publishable: boolean; issues: AssessmentQualityIssue[] };
};

export type AssessmentDraftUpdatePayload = Pick<
  AssessmentDraft,
  | "pass_threshold"
  | "mastery_threshold"
  | "max_attempts"
  | "assessment_mode"
  | "answer_reveal_policy"
  | "shuffle_questions"
  | "shuffle_options"
  | "items"
> & { expected_revision: number };

export type StudentAssessmentItem = {
  assessment_item_id: string;
  position: number;
  item_type: string;
  prompt: Record<string, unknown>;
  max_score: number;
  knowledge_point_ids: string[];
};

export type StudentAssessment = {
  assessment_version_id: string;
  task_id: string;
  assessment_mode: "closed_book" | "open_book";
  max_attempts: number;
  items: StudentAssessmentItem[];
};

export type AssessmentAttempt = {
  attempt_id: string;
  assessment_version_id: string;
  task_id: string;
  attempt_number: number;
  status: "in_progress" | "graded" | "pending_review";
  draft_revision: number;
  submitted_at: string | null;
  auto_score: number | null;
  final_score: number | null;
  result: "needs_retry" | "passed" | "mastered" | "pending_review" | null;
};

export type AssessmentFeedbackItem = {
  assessment_item_id: string;
  position: number;
  item_type: string;
  prompt: Record<string, unknown>;
  answer?: Record<string, unknown> | null;
  final_score?: number | null;
  max_score: number;
  review_status: string;
  student_comment?: string | null;
  solution?: Record<string, unknown>;
  rubric?: Record<string, unknown>;
};

export type AssessmentFeedback = {
  assessment_assignment_id: string;
  task_id: string;
  attempts_used: number;
  max_attempts: number;
  best_final_score: number | null;
  result: "not_attempted" | "needs_retry" | "passed" | "mastered" | "pending_review";
  answers_revealed_at: string | null;
  items: AssessmentFeedbackItem[];
};

export type AssessmentRatio = { numerator: number; denominator: number; rate: number };

export type AssessmentAnalyticsReviewItem = {
  assessment_item_id: string;
  prompt: Record<string, unknown>;
  answer: Record<string, unknown>;
  rubric: Record<string, unknown>;
  max_score: number;
  ai_suggestion: Record<string, unknown> | null;
};

export type AssessmentAnalyticsStudent = {
  student_id: string;
  status: string;
  attempts_used: number;
  max_attempts: number;
  best_final_score: number | null;
  result: string;
  attempts: AssessmentAttempt[];
  review_attempt_id: string | null;
  review_items: AssessmentAnalyticsReviewItem[];
};

export type AssessmentAnalytics = {
  task_id: string;
  enrolled: number;
  participation: AssessmentRatio;
  submission: AssessmentRatio;
  pass: AssessmentRatio;
  mastery: AssessmentRatio;
  pending_review: number;
  mean_best_score: number | null;
  median_best_score: number | null;
  average_attempts: number;
  score_distribution: Array<{ label: string; count: number }>;
  students: AssessmentAnalyticsStudent[];
  items: Array<{ assessment_item_id: string; position: number; prompt: Record<string, unknown>; sample_count: number; full_score_count: number; full_score_rate: AssessmentRatio }>;
  knowledge_points: Array<{ knowledge_point_id: string; sample_count: number; full_score_count: number; full_score_rate: AssessmentRatio }>;
};

export type LearningEventPayload = {
  event_id: string;
  event_type: "started" | "resource_opened" | "progress_updated" | "resource_completed" | "completed";
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
  origin_type?: "personal" | "standard" | "legacy_shared";
  standard_kind?: StandardResourceKind | null;
  current_review_status?: string;
  approved_version?: number | null;
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
    required?: boolean;
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
  source_type?: string | null;
  generation_review_score?: number | null;
  generation_audit?: Record<string, unknown> | null;
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
  english_query?: string;
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
  review_status: "discovered" | "relevant" | "rejected_irrelevant" | "fetch_failed" | "ready" | "approved" | "rejected" | "pending";
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

export type CourseKnowledgeBuildConfig = {
  preset: "small" | "standard" | "large" | "custom";
  graph_depth: number;
  target_module_count: number;
  target_points_per_module: number;
  target_materials_per_leaf: number;
  minimum_web_materials_per_leaf: number;
  maximum_ai_materials_per_leaf: number;
  max_search_results_per_leaf: number;
  prefer_complete_textbooks: boolean;
  max_online_textbooks: number;
  max_search_rounds_per_leaf: number;
  ai_supplement_enabled: boolean;
  content_language: string;
  update_strategy: "incremental" | "merge_rebuild" | "full_rebuild";
};

export type CourseKnowledgeTextbookOutlineItem = {
  id: string;
  title: string;
  level: number;
  line_index?: number;
  page?: number | null;
  sections?: CourseKnowledgeTextbookOutlineItem[];
};

export type CourseKnowledgeTextbookInput = {
  textbook_id: string;
  filename: string;
  extension: ".pdf" | ".docx" | ".txt" | ".md";
  size_bytes: number;
  content_hash: string;
  status: "queued" | "parsing" | "ready" | "failed";
  uploaded_by: string;
  uploaded_at: string;
  parse_result?: {
    parser: string;
    summary: string;
    outline: CourseKnowledgeTextbookOutlineItem[];
    char_count: number;
    chapter_count: number;
    chunk_count: number;
    warnings: string[];
    parsed_at: string;
  } | null;
  error?: { code?: string; message?: string } | null;
};

export type CourseKnowledgeBuild = {
  build_id: string;
  library_id?: string;
  course_id: string;
  status: "draft" | "queued" | "running" | "publishing" | "succeeded" | "failed" | "blocked" | "canceled";
  phase: string;
  progress?: number;
  revision: number;
  graph_confirmed_at?: string | null;
  confirmed_graph_revision?: number | null;
  confirmed_by?: string | null;
  config?: CourseKnowledgeBuildConfig;
  textbooks?: CourseKnowledgeTextbookInput[];
  course_snapshot: Record<string, unknown>;
  topics: CourseKnowledgeTopic[];
  graph_draft?: KnowledgeGraphNode | null;
  baseline_graph_version?: number | null;
  baseline_graph?: KnowledgeGraphNode | null;
  current_graph_summary?: {
    root_id: string;
    root_label: string;
    node_count: number;
    leaf_count: number;
    modules: Array<{ id: string; label: string; child_count: number }>;
  } | null;
  source_candidates: CourseKnowledgeSourceCandidate[];
  warnings: string[];
  metrics?: Record<string, unknown>;
  quality_score?: number | null;
  quality_checks?: CourseKnowledgeQualityCheck[];
  error?: { code?: string; message?: string } | null;
  graph_generation_error?: { code?: string; message?: string; issues?: Array<Record<string, unknown>> } | null;
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
    document_ids?: string[];
    source_outline_refs?: string[];
    unmapped_outline_items?: string[];
    validation?: {
      status?: string;
      node_count?: number;
      module_count?: number;
      leaf_count?: number;
      max_depth?: number;
      target_module_count?: number;
      target_leaf_count?: number;
      mapped_outline_count?: number;
      unmapped_outline_count?: number;
    };
    edited_at?: string;
    edited_by?: string;
    review_state?: "existing" | "new" | "needs_review" | "needs_parent";
    needs_parent?: boolean;
  };
};

export type KnowledgeGraphData = {
  root: KnowledgeGraphNode;
};

export type StandardResourceKind = "classroom" | "study_guide" | "practice";

export type StandardResourceSlot = {
  standard_kind: StandardResourceKind;
  material_type: string;
  material_id: string;
  review_status: string;
  current_version?: number | null;
  approved_version?: number | null;
  resource?: CourseMaterial | null;
};

export type StandardResourceLeaf = {
  leaf_id: string;
  title: string;
  chapter_id?: string | null;
  chapter_title?: string | null;
  path_titles: string[];
  slots: StandardResourceSlot[];
};

export type StandardResourceCatalog = {
  course_id: string;
  leaves: StandardResourceLeaf[];
};

export type ClassroomCatalogProgress = Pick<
  ResourceLearningProgress,
  | "resource_id"
  | "resource_version"
  | "status"
  | "completion_basis"
  | "explanation_coverage_percent"
  | "answered_question_count"
  | "required_question_count"
  | "completed_at"
  | "last_activity_at"
>;

export type ClassroomCatalogResource = StandardResourceSlot & {
  progress?: ClassroomCatalogProgress | null;
};

export type ClassroomCatalogLeaf = Omit<StandardResourceLeaf, "slots"> & {
  resources: ClassroomCatalogResource[];
  summary?: { pending: number; published: number };
  learning_summary?: { completed: number; total: number };
};

export type ClassroomCatalog = {
  course_id: string;
  mode: "manage" | "learn";
  leaves: ClassroomCatalogLeaf[];
};

export type StandardResourceBatchItem = {
  batch_item_id: string;
  batch_id: string;
  leaf_id: string;
  leaf_title: string;
  standard_kind: StandardResourceKind;
  material_type: string;
  material_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  job_id?: string | null;
  attempt_count: number;
  error?: { code?: string; message?: string } | null;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
};

export type StandardResourceBatch = {
  batch_id: string;
  course_id: string;
  created_by: string;
  status: "queued" | "running" | "partial" | "completed" | "failed";
  total_items: number;
  queued_items: number;
  running_items: number;
  succeeded_items: number;
  failed_items: number;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
  items: StandardResourceBatchItem[];
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
  required?: boolean;
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
  owner_user_id?: string | null;
  visibility?: "private" | "course" | string;
  video_status?: "queued" | "running" | "ready" | "failed" | string;
  video_url?: string | null;
  stage?: { id: string; name?: string; [key: string]: unknown };
  scenes?: ClassroomScene[];
  scenes_count?: number;
  voice_status?: string;
  sidecar_url?: string;
  sidecar_created_at?: string;
  course_id?: string;
  created_at?: string;
  updated_at?: string;
  version?: number;
  content_hash?: string;
};

export type ResourceLearningSceneKind = "explanation" | "exercise" | "demo";

export type ResourceLearningManifestScene = {
  scene_id: string;
  kind: ResourceLearningSceneKind;
  expected_duration_ms: number;
  required_action_ids: string[];
  required_question_ids: string[];
};

export type ResourceLearningManifest = {
  manifest_id: string;
  resource_version: number;
  content_hash: string;
  mode: "completable" | "behavior_only";
  scenes: ResourceLearningManifestScene[];
  required_question_ids: string[];
};

export type ResourceLearningProgress = {
  course_id: string;
  resource_id: string;
  resource_version: number;
  status: "not_started" | "in_progress" | "completed";
  completion_basis?:
    | "classroom_requirements"
    | "required_questions_submitted"
    | "explicit_read"
    | null;
  explanation_covered_ms: number;
  explanation_total_ms: number;
  explanation_coverage_percent: number;
  required_question_count: number;
  answered_question_count: number;
  question_completion_percent: number;
  correct_count_first: number;
  correct_count_latest: number;
  demo_view_count: number;
  demo_interaction_count: number;
  started_at: string | null;
  completed_at: string | null;
  last_activity_at: string | null;
  updated_at: string;
  manifest?: ResourceLearningManifest | null;
};

export type ResourceLearningSession = {
  session_id: string;
  course_id: string;
  resource_id: string;
  resource_version: number;
  status: "active" | "ended" | "invalidated";
  started_at: string;
  last_heartbeat_at: string | null;
  ended_at: string | null;
};

export type ResourceLearningEventType =
  | "scene_entered"
  | "timeline_heartbeat"
  | "playback_paused"
  | "scene_completed"
  | "demo_entered"
  | "demo_interacted"
  | "demo_completed";

export type ResourceLearningEventPayload = {
  event_id: string;
  sequence_number: number;
  event_type: ResourceLearningEventType;
  scene_id: string;
  timeline_from_ms?: number;
  timeline_to_ms?: number;
  action_id?: string;
  occurred_at: string;
};

export type ResourceLearningAnalytics = {
  course_id: string;
  resource_id: string;
  resource_version: number;
  enrolled_student_count: number;
  tracked_student_count: number;
  started_student_count: number;
  completed_student_count: number;
  in_progress_student_count: number;
  not_started_student_count: number;
  average_explanation_coverage_percent: number;
  average_question_completion_percent: number;
  completion_rate: number;
  completion_rate_ratio: { numerator: number; denominator: number; percent: number };
  all_questions_answered_student_count: number;
  demo_view_student_count: number;
  demo_interaction_student_count: number;
  demo_view_count: number;
  demo_interaction_count: number;
  queues: Record<string, number>;
  question_analytics: Array<{
    question_id: string;
    response_rate: { numerator: number; denominator: number; percent: number };
    first_correct_rate: { numerator: number; denominator: number; percent: number };
    latest_correct_rate: { numerator: number; denominator: number; percent: number };
    option_distribution: Array<{ value: string; count: number }>;
  }>;
  knowledge_point_errors: Array<{
    knowledge_point_id: string;
    incorrect_student_count: number;
    incorrect_attempt_count: number;
  }>;
};

export type QuizAnswers = Record<string, string | string[]>;

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

export type ResourceQaKind = "study_guide" | "practice";

export type ResourceQaAnchor = {
  scene_id?: string | null;
  page_number?: number | null;
  question_id?: string | null;
};

export type ResourceQaTurnRequest = {
  client_turn_id: string;
  question: string;
  resource_version: number;
  context_scope: "full_resource";
  anchor: ResourceQaAnchor | null;
};

export type ResourceQaTurn = ClassroomQaTurn;

export type ResourceQaSession = {
  session_id: string;
  course_id: string;
  resource_kind: ResourceQaKind;
  resource_id: string;
  resource_version: number;
  owner_user_id: string;
  status: "ready";
  turns: ResourceQaTurn[];
};

export type ResourceQaTurnSubmission = {
  session_id: string;
  turn: ResourceQaTurn;
};
