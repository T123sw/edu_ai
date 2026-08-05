const BACKEND_BASE_URL =
  (typeof import.meta !== 'undefined' ? (import.meta as any).env?.VITE_API_BASE_URL : undefined) ||
  'http://localhost:8001';
const AUTH_STORAGE_KEY = 'edu-ai-auth';

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || null;
  } catch {
    return null;
  }
}

export interface ChatReplyRequestV2 {
  question: string;
  conversation_id?: string;
  model_id?: string;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  artifact_id?: string;
  allow_rag?: boolean;
  allow_web?: boolean;
  selected_doc_ids?: string[];
  input_images?: ChatInputImageV2[];
  input_videos?: ChatInputVideoV2[];
  action_hint?: string;
  artifact_reference?: ChatArtifactReference;
  conversation_reference?: ChatConversationReference;
}

export interface ChatInputImageV2 {
  image_id: string;
  file_name: string;
  mime_type: string;
  storage_path: string;
  relative_path: string;
  image_url: string;
  source: 'upload' | 'paste';
}

export interface ChatInputVideoV2 {
  video_id: string;
  file_name: string;
  mime_type: string;
  storage_path: string;
  relative_path: string;
  video_url: string;
  source: 'upload';
}

export interface ChatImageUploadResponseV2 {
  conversation_id?: string;
  session_id: string;
  images: ChatInputImageV2[];
}

export interface ChatVideoUploadResponseV2 {
  conversation_id?: string;
  session_id: string;
  videos: ChatInputVideoV2[];
}

export interface ChatArtifactReference {
  artifact_id: string;
  artifact_type: 'report' | 'report_outline';
  version_id?: string;
  title?: string;
  source_conversation_id?: string;
  source_course_id?: string;
}

export interface ChatConversationReference {
  conversation_id: string;
  title?: string;
  message_count?: number;
}

export interface ChatReportRequestV2 {
  question: string;
  conversation_id?: string;
  model_id?: string;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  allow_rag?: boolean;
  allow_web?: boolean;
  selected_doc_ids?: string[];
  report_config?: Record<string, unknown> | null;
  entry_mode?: 'knowledge_base_report' | 'chat_report';
  prompt_draft?: string;
  final_user_prompt?: string;
  selected_card?: ReportEntryCardSelection | null;
}

export interface ChatReportCardsRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
}

export interface ChatPptCardsRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
}

export interface ChatLessonPlanCardsRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
}

export interface KnowledgeBaseDirectReportRequestV2 {
  question: string;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
  report_config?: Record<string, unknown> | null;
  prompt_draft?: string;
  final_user_prompt?: string;
  selected_card?: ReportEntryCardSelection | null;
}

export type QuizQuestionTypeV2 = 'choice' | 'blank' | 'short' | 'judge';
export type QuizDifficultyV2 = 'easy' | 'medium' | 'hard';

export interface KnowledgeBaseDirectQuizPrefillRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
}

export interface DirectQuizConfigV2 {
  topic: string;
  hard_points: string[];
  difficulty: QuizDifficultyV2;
  question_count: number;
  question_types: QuizQuestionTypeV2[];
  include_answers: boolean;
  include_explanations: boolean;
}

export interface KnowledgeBaseDirectQuizRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
  quiz_config: DirectQuizConfigV2;
  prompt_draft?: string;
  final_user_prompt?: string;
}

export type GameTypeV2 = 'category_sort' | 'drag_match' | 'memory_flip';

export interface KnowledgeBaseDirectGameRequestV2 {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
  game_type: GameTypeV2;
}

export interface KnowledgeBaseDirectFlashcardRequestV2 {
  course_id: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids: string[];
  flashcard_config: {
    title?: string;
    count: number;
    difficulty: 'easy' | 'medium' | 'hard';
    category?: string;
    show_sources: boolean;
  };
  idempotency_key: string;
}

export interface KnowledgeBaseDirectPptOutlineRequestV2 {
  course_id: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids: string[];
  ppt_config: {
    deck_title: string;
    deck_subtitle?: string;
    audience?: string;
    objective?: string;
    theme_id: 'heu_academic_elegant' | 'heu_academic_basic';
    length_option: 'short' | 'medium' | 'long';
    target_slide_count?: number;
    key_points: string[];
    style_hint?: string;
    special_requirements?: string;
    general_requirements?: string;
  };
}

export interface KnowledgeBaseDirectPptGenerateRequestV2 {
  draft_id: string;
  confirm: true;
  outline?: Record<string, unknown>;
  idempotency_key: string;
}

export interface KnowledgeBaseDirectGraphRequestV2 {
  course_id: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids: string[];
  title?: string;
  max_depth: number;
  idempotency_key: string;
}

export interface KnowledgeBaseDirectBlogRequestV2 {
  course_id: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  selected_doc_ids?: string[];
  topic: string;
  idempotency_key: string;
}

export interface ChatDirectPptOutlineResponseV2 {
  action: { name: string };
  draft: { draft_id: string; status: string };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ReportEntryCardSelection {
  card_id: string;
  card_type: 'preset' | 'recommended';
  preset_key?: 'brief' | 'detailed' | 'study_plan' | 'custom';
  recommendation_type?:
    | 'summary'
    | 'comparison'
    | 'risk_analysis'
    | 'teaching_suggestion'
    | 'study_focus'
    | 'theme_outline';
}

export interface PptEntryCardSelection {
  card_id: string;
  card_type: 'preset' | 'recommended';
  preset_key?: 'knowledge_lecture' | 'topic_briefing' | 'comparison_analysis' | 'defense_summary';
  recommendation_type?: 'concept_focus' | 'process_flow' | 'comparison_view' | 'case_application';
}

export interface LessonPlanEntryCardPrefillConfig {
  topic: string;
  audience?: string;
  duration?: string;
  lesson_type?: string;
  objective?: string;
  key_points?: string[];
  difficult_points?: string[];
  after_class_task?: string;
  style_hint?: string;
}

export interface ReportEntryCard {
  card_id: string;
  card_type: 'preset' | 'recommended';
  title: string;
  description: string;
  prompt_draft: string;
  preset_key?: 'brief' | 'detailed' | 'study_plan' | 'custom';
  recommendation_type?:
    | 'summary'
    | 'comparison'
    | 'risk_analysis'
    | 'teaching_suggestion'
    | 'study_focus'
    | 'theme_outline';
  recommendation_source?: 'doc_summaries';
  fit_score?: 'high' | 'medium' | 'low';
}

export interface PptEntryCard {
  card_id: string;
  card_type: 'preset' | 'recommended';
  title: string;
  description: string;
  objective_hint?: string;
  length_option?: 'short' | 'medium' | 'long';
  preset_key?: 'knowledge_lecture' | 'topic_briefing' | 'comparison_analysis' | 'defense_summary';
  recommendation_type?: 'concept_focus' | 'process_flow' | 'comparison_view' | 'case_application';
  recommendation_source?: 'doc_summaries';
  fit_score?: 'high' | 'medium' | 'low';
  style_hint?: string;
}

export interface LessonPlanEntryCard {
  card_id: string;
  card_type: 'preset' | 'recommended';
  title: string;
  description: string;
  prompt_draft: string;
  prefill_config?: LessonPlanEntryCardPrefillConfig;
  preset_key?: 'new_lesson' | 'review_lesson' | 'inquiry_lesson' | 'practice_lesson';
  recommendation_type?:
    | 'knowledge_building'
    | 'historical_inquiry'
    | 'practice_consolidation'
    | 'review_summary'
    | 'material_analysis';
  recommendation_source?: 'doc_summaries';
  fit_score?: 'high' | 'medium' | 'low';
}

export interface ChatReportCardsResponseV2 {
  entry_mode: 'knowledge_base_report';
  cards: ReportEntryCard[];
  trace?: Record<string, unknown>;
}

export interface ChatPptCardsResponseV2 {
  entry_mode: 'knowledge_base_ppt';
  cards: PptEntryCard[];
  trace?: Record<string, unknown>;
}

export interface ChatLessonPlanCardsResponseV2 {
  entry_mode: 'knowledge_base_lesson_plan';
  cards: LessonPlanEntryCard[];
  default_selected_card_id?: string;
  trace?: Record<string, unknown>;
}

export interface ChatDirectReportResponseV2 {
  action: {
    name: string;
  };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ChatQuizPrefillResponseV2 {
  entry_mode: 'knowledge_base_quiz';
  topic: string;
  hard_points: string[];
  trace: Record<string, unknown>;
}

export interface ChatDirectQuizResponseV2 {
  action: {
    name: string;
  };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ChatDirectGameResponseV2 {
  action: {
    name: string;
  };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ChatDirectTaskSubmittedV2 {
  task_id: string;
  status: 'pending';
  workflow_type: string;
}

export interface StatusCardEvidenceDetail {
  content: string;
  source_type?: string;
  confidence?: string;
  source_message_count?: number;
}

export interface StatusCardV2 {
  mode: 'chat' | 'workflow';
  status_label: string;
  workflow_label?: string;
  topics?: string[];
  goal?: string;
  issues?: string[];
  confirmed_facts?: string[];
  student_signals?: string[];
  evidence_points?: string[];
  evidence_details?: StatusCardEvidenceDetail[];
  extra_constraints?: string[];
  source_labels?: string[];
  active_artifact_label?: string;
  waiting_label?: string;
  suggested_actions?: string[];
  audience?: string;
  tone?: string;
  length?: string;
  grade_level?: string;
  subject?: string;
  allow_rag?: boolean;
  allow_web?: boolean;
  summary_hint?: string;
}

export interface ChatSourceV2 {
  source?: string;
  content?: string;
  modality?: string;
  image_url?: string;
  video_url?: string;
  source_path?: string;
  metadata?: {
    modality?: string;
    image_url?: string;
    video_url?: string;
    stream_url?: string;
    playback_url?: string;
    title?: string;
    start_time?: number;
    end_time?: number;
  };
  [key: string]: unknown;
}

export interface ChatResponseV2 {
  message: {
    role: string;
    content: string;
  };
  conversation: {
    conversation_id: string;
  };
  action: {
    name: string;
  };
  workflow?: Record<string, unknown> | null;
  artifacts: Array<Record<string, unknown>>;
  sources: ChatSourceV2[];
  trace: Record<string, unknown>;
  status_card?: StatusCardV2 | null;
}

export interface ChatErrorResponseV2 {
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
  };
  detail?: string;
}

export type ChatStreamEventTypeV2 =
  | 'metadata'
  | 'status'
  | 'delta'
  | 'result'
  | 'done'
  | 'error'
  | 'task_submitted'
  | 'plan'
  | 'plan_step_update'
  | 'tool_call'
  | 'tool_result'
  | 'reflect';

export interface ChatStreamEventV2 {
  type: ChatStreamEventTypeV2;
  payload: Record<string, any>;
}

// ReAct agent plan event payloads (mirrors Edu_AI/api/src/app/chat/runtime/planning/schema.py).
export interface AgentPlanStepV2 {
  index: number;
  user_title: string;
  internal_action: string;
  expected_tools: string[];
  constraints?: Record<string, any>;
  status?: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
}

export interface AgentPlanV2 {
  subject: string;
  resource_type: string;
  steps: AgentPlanStepV2[];
}

export interface AgentPlanStepUpdateV2 {
  step_index: number;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  user_title?: string;
}

export interface AgentToolCallV2 {
  tool: string;
  args: Record<string, any>;
}

export interface AgentToolResultV2 {
  tool: string;
  summary: string;
  ok: boolean;
  /** Tool-specific extras forwarded for rich UI rendering (e.g. outline_markdown). */
  outline_markdown?: string;
  resource_type?: string;
  subject?: string;
}

export interface AgentReflectV2 {
  tool: string;
  verdict: string;
  severity: string;
  issue: string;
}

export interface ChatReplyStreamHandlersV2 {
  onMetadata?: (payload: Record<string, any>) => void;
  onStatus?: (payload: Record<string, any>) => void;
  onDelta?: (content: string, payload: Record<string, any>) => void;
  onResult?: (response: ChatResponseV2) => void;
  onTaskSubmitted?: (taskId: string, workflowType: string, payload: Record<string, any>) => void;
  onDone?: (payload: Record<string, any>) => void;
  onError?: (error: Error, payload?: Record<string, any>) => void;
  // ReAct agent events (Phase 2-5 SSE additions)
  onPlan?: (plan: AgentPlanV2) => void;
  onPlanStepUpdate?: (update: AgentPlanStepUpdateV2) => void;
  onToolCall?: (call: AgentToolCallV2) => void;
  onToolResult?: (result: AgentToolResultV2) => void;
  onReflect?: (reflect: AgentReflectV2) => void;
}

export interface ChatTaskStatusV2 {
  task_id: string;
  workflow_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: ChatResponseV2 | null;
  error?: string | null;
  created_at: string;
}

export async function pollChatTask(taskId: string): Promise<ChatTaskStatusV2> {
  const token = getAuthToken();
  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/tasks/${taskId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new Error(`任务查询失败: ${resp.status} ${resp.statusText}`);
  return (await resp.json()) as ChatTaskStatusV2;
}

export interface SpeechTranscriptResponseV2 {
  text: string;
}

async function postV2<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
  const token = getAuthToken();
  const resp = await fetch(`${BACKEND_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    let detail = `请求失败: ${resp.status} ${resp.statusText}`;
    try {
      const errorPayload = (await resp.json()) as ChatErrorResponseV2;
      detail = errorPayload.error?.message || errorPayload.detail || detail;
    } catch {
      const text = await resp.text().catch(() => '');
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await resp.json()) as TResponse;
}

export async function sendChatReplyV2(payload: ChatReplyRequestV2): Promise<ChatResponseV2> {
  return postV2<ChatResponseV2, ChatReplyRequestV2>('/api/chat/v2/reply', payload);
}

export function parseChatReplyV2StreamChunk(
  previousRemainder: string,
  chunk: string,
): { events: ChatStreamEventV2[]; remainder: string } {
  const combined = `${previousRemainder || ''}${chunk || ''}`;
  const parts = combined.split(/\r?\n\r?\n/);
  const remainder = parts.pop() || '';
  const events = parts
    .map((frame) =>
      frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join(''),
    )
    .filter(Boolean)
    .map((data) => JSON.parse(data) as ChatStreamEventV2);
  return { events, remainder };
}

export async function sendChatReplyV2Stream(
  payload: ChatReplyRequestV2,
  handlers: ChatReplyStreamHandlersV2,
): Promise<void> {
  const token = getAuthToken();
  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/v2/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败: ${resp.status} ${resp.statusText}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let remainder = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseChatReplyV2StreamChunk(remainder, decoder.decode(value, { stream: true }));
    remainder = parsed.remainder;
    for (const event of parsed.events) {
      if (event.type === 'metadata') handlers.onMetadata?.(event.payload);
      else if (event.type === 'status') handlers.onStatus?.(event.payload);
      else if (event.type === 'delta') handlers.onDelta?.(String(event.payload?.content || ''), event.payload);
      else if (event.type === 'result') handlers.onResult?.(event.payload as ChatResponseV2);
      else if (event.type === 'task_submitted') {
        const taskId = String(event.payload?.task_id || '');
        const workflowType = String(event.payload?.workflow_type || '');
        handlers.onTaskSubmitted?.(taskId, workflowType, event.payload);
      }
      else if (event.type === 'plan') handlers.onPlan?.(event.payload as AgentPlanV2);
      else if (event.type === 'plan_step_update') handlers.onPlanStepUpdate?.(event.payload as AgentPlanStepUpdateV2);
      else if (event.type === 'tool_call') handlers.onToolCall?.(event.payload as AgentToolCallV2);
      else if (event.type === 'tool_result') handlers.onToolResult?.(event.payload as AgentToolResultV2);
      else if (event.type === 'reflect') handlers.onReflect?.(event.payload as AgentReflectV2);
      else if (event.type === 'done') handlers.onDone?.(event.payload);
      else if (event.type === 'error') handlers.onError?.(new Error(String(event.payload?.message || '流式回复失败')), event.payload);
    }
  }
}

export async function uploadChatImagesV2(
  files: File[],
  options?: { conversationId?: string | null; source?: 'upload' | 'paste' },
): Promise<ChatImageUploadResponseV2> {
  const token = getAuthToken();
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file, file.name);
  }
  if (options?.conversationId) {
    formData.append('conversation_id', options.conversationId);
  }
  formData.append('source', options?.source || 'upload');

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/v2/images/upload`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!resp.ok) {
    let detail = `请求失败: ${resp.status} ${resp.statusText}`;
    try {
      const errorPayload = (await resp.json()) as ChatErrorResponseV2;
      detail = errorPayload.error?.message || errorPayload.detail || detail;
    } catch {
      const text = await resp.text().catch(() => '');
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await resp.json()) as ChatImageUploadResponseV2;
}

export async function uploadChatVideosV2(
  files: File[],
  options?: { conversationId?: string | null; source?: 'upload' },
): Promise<ChatVideoUploadResponseV2> {
  const token = getAuthToken();
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file, file.name);
  }
  if (options?.conversationId) {
    formData.append('conversation_id', options.conversationId);
  }
  formData.append('source', options?.source || 'upload');

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/v2/videos/upload`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!resp.ok) {
    let detail = `璇锋眰澶辫触: ${resp.status} ${resp.statusText}`;
    try {
      const errorPayload = (await resp.json()) as ChatErrorResponseV2;
      detail = errorPayload.error?.message || errorPayload.detail || detail;
    } catch {
      const text = await resp.text().catch(() => '');
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await resp.json()) as ChatVideoUploadResponseV2;
}

export async function sendReportV2(payload: ChatReportRequestV2): Promise<ChatResponseV2> {
  return postV2<ChatResponseV2, ChatReportRequestV2>('/api/chat/v2/report', payload);
}

export async function fetchReportEntryCardsV2(
  payload: ChatReportCardsRequestV2,
): Promise<ChatReportCardsResponseV2> {
  return postV2<ChatReportCardsResponseV2, ChatReportCardsRequestV2>('/api/chat/v2/report/cards', payload);
}

export async function fetchPptEntryCardsV2(payload: ChatPptCardsRequestV2): Promise<ChatPptCardsResponseV2> {
  return postV2<ChatPptCardsResponseV2, ChatPptCardsRequestV2>('/api/chat/v2/ppt/cards', payload);
}

export async function fetchLessonPlanEntryCardsV2(
  payload: ChatLessonPlanCardsRequestV2,
): Promise<ChatLessonPlanCardsResponseV2> {
  return postV2<ChatLessonPlanCardsResponseV2, ChatLessonPlanCardsRequestV2>(
    '/api/chat/v2/lesson-plan/cards',
    payload,
  );
}

export async function generateKnowledgeBaseReportV2(
  payload: KnowledgeBaseDirectReportRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectReportRequestV2>('/api/chat/v2/report/direct', payload);
}

export async function fetchQuizEntryPrefillV2(
  payload: KnowledgeBaseDirectQuizPrefillRequestV2,
): Promise<ChatQuizPrefillResponseV2> {
  return postV2<ChatQuizPrefillResponseV2, KnowledgeBaseDirectQuizPrefillRequestV2>('/api/chat/v2/quiz/prefill', payload);
}

export async function generateKnowledgeBaseQuizV2(
  payload: KnowledgeBaseDirectQuizRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectQuizRequestV2>('/api/chat/v2/quiz/direct', payload);
}

export async function generateKnowledgeBaseGameV2(
  payload: KnowledgeBaseDirectGameRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectGameRequestV2>('/api/chat/v2/game/direct', payload);
}

export async function generateKnowledgeBaseFlashcardV2(
  payload: KnowledgeBaseDirectFlashcardRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectFlashcardRequestV2>(
    '/api/chat/v2/flashcard/direct',
    payload,
  );
}

export async function generateKnowledgeBasePptOutlineV2(
  payload: KnowledgeBaseDirectPptOutlineRequestV2,
): Promise<ChatDirectPptOutlineResponseV2> {
  return postV2<ChatDirectPptOutlineResponseV2, KnowledgeBaseDirectPptOutlineRequestV2>(
    '/api/chat/v2/ppt/outline',
    payload,
  );
}

export async function generateKnowledgeBasePptV2(
  payload: KnowledgeBaseDirectPptGenerateRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectPptGenerateRequestV2>(
    '/api/chat/v2/ppt/generate',
    payload,
  );
}

export async function generateKnowledgeBaseGraphV2(
  payload: KnowledgeBaseDirectGraphRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectGraphRequestV2>(
    '/api/chat/v2/graph/direct',
    payload,
  );
}

export async function generateKnowledgeBaseBlogV2(
  payload: KnowledgeBaseDirectBlogRequestV2,
): Promise<ChatDirectTaskSubmittedV2> {
  return postV2<ChatDirectTaskSubmittedV2, KnowledgeBaseDirectBlogRequestV2>(
    '/api/chat/v2/blog/direct',
    payload,
  );
}

export async function transcribeSpeechV2(file: Blob, filename: string): Promise<SpeechTranscriptResponseV2> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file, filename);

  const resp = await fetch(`${BACKEND_BASE_URL}/api/speech/transcribe`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!resp.ok) {
    let detail = `请求失败: ${resp.status} ${resp.statusText}`;
    try {
      const errorPayload = (await resp.json()) as ChatErrorResponseV2;
      detail = errorPayload.error?.message || errorPayload.detail || detail;
    } catch {
      const text = await resp.text().catch(() => '');
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await resp.json()) as SpeechTranscriptResponseV2;
}

interface BuildChatReplyPayloadOptions {
  question: string;
  conversationId?: string | null;
  courseId?: string;
  scopeType?: 'course' | 'knowledge_point';
  scopeId?: string;
  allowRag: boolean;
  allowWeb: boolean;
  selectedDocIds: string[];
  inputImages?: ChatInputImageV2[];
  inputVideos?: ChatInputVideoV2[];
  artifactReference?: ChatArtifactReference | null;
  conversationReference?: ChatConversationReference | null;
}

export function buildChatReplyPayload(options: BuildChatReplyPayloadOptions): ChatReplyRequestV2 {
  const payload: ChatReplyRequestV2 = {
    question: options.question,
    conversation_id: options.conversationId || undefined,
    course_id: options.courseId,
    scope_type: options.scopeType,
    scope_id: options.scopeId,
    allow_rag: options.allowRag,
    allow_web: options.allowWeb,
    selected_doc_ids: options.selectedDocIds,
  };
  if (options.artifactReference) {
    payload.artifact_reference = options.artifactReference;
  }
  if (options.conversationReference) {
    payload.conversation_reference = options.conversationReference;
  }
  if (options.inputImages?.length) {
    payload.input_images = options.inputImages;
  }
  if (options.inputVideos?.length) {
    payload.input_videos = options.inputVideos;
  }
  return payload;
}
