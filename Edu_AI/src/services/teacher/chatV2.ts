const BACKEND_BASE_URL =
  (typeof import.meta !== 'undefined' ? (import.meta as any).env?.VITE_API_BASE_URL : undefined) ||
  (typeof window !== 'undefined' ? window.location.origin : '');
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
  artifact_id?: string;
  allow_rag?: boolean;
  allow_web?: boolean;
  selected_doc_ids?: string[];
  action_hint?: string;
  artifact_reference?: ChatArtifactReference;
  conversation_reference?: ChatConversationReference;
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
  selected_doc_ids?: string[];
}

export interface ChatPptCardsRequestV2 {
  course_id?: string;
  selected_doc_ids?: string[];
}

export interface KnowledgeBaseDirectReportRequestV2 {
  question: string;
  course_id?: string;
  selected_doc_ids?: string[];
  report_config?: Record<string, unknown> | null;
  prompt_draft?: string;
  final_user_prompt?: string;
  selected_card?: ReportEntryCardSelection | null;
}

export interface KnowledgeBaseDirectPptOutlineRequestV2 {
  course_id?: string;
  selected_doc_ids?: string[];
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
    selected_card?: PptEntryCardSelection | null;
  };
}

export interface KnowledgeBaseDirectPptGenerateRequestV2 {
  draft_id: string;
  confirm: boolean;
  outline?: Record<string, unknown>;
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

export interface ChatDirectReportResponseV2 {
  action: {
    name: string;
  };
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ChatDirectPptOutlineResponseV2 {
  action: {
    name: string;
  };
  draft: Record<string, unknown>;
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
}

export interface ChatDirectPptGenerateResponseV2 {
  action: {
    name: string;
  };
  run: Record<string, unknown>;
  artifacts: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
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
  sources: Array<Record<string, unknown>>;
  trace: Record<string, unknown>;
  status_card?: StatusCardV2 | null;
}

export interface ChatErrorResponseV2 {
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
  };
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
      detail = errorPayload.error?.message || detail;
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

export async function generateKnowledgeBaseReportV2(
  payload: KnowledgeBaseDirectReportRequestV2,
): Promise<ChatDirectReportResponseV2> {
  return postV2<ChatDirectReportResponseV2, KnowledgeBaseDirectReportRequestV2>('/api/chat/v2/report/direct', payload);
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
): Promise<ChatDirectPptGenerateResponseV2> {
  return postV2<ChatDirectPptGenerateResponseV2, KnowledgeBaseDirectPptGenerateRequestV2>(
    '/api/chat/v2/ppt/generate',
    payload,
  );
}

interface BuildChatReplyPayloadOptions {
  question: string;
  conversationId?: string | null;
  courseId?: string;
  allowRag: boolean;
  allowWeb: boolean;
  selectedDocIds: string[];
  artifactReference?: ChatArtifactReference | null;
  conversationReference?: ChatConversationReference | null;
}

export function buildChatReplyPayload(options: BuildChatReplyPayloadOptions): ChatReplyRequestV2 {
  const payload: ChatReplyRequestV2 = {
    question: options.question,
    conversation_id: options.conversationId || undefined,
    course_id: options.courseId,
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
  return payload;
}
