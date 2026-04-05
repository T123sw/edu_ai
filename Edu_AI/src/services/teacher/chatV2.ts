const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin;
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

async function postV2<TPayload>(path: string, payload: TPayload): Promise<ChatResponseV2> {
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

  return (await resp.json()) as ChatResponseV2;
}

export async function sendChatReplyV2(payload: ChatReplyRequestV2): Promise<ChatResponseV2> {
  return postV2('/api/chat/v2/reply', payload);
}

export async function sendReportV2(payload: ChatReportRequestV2): Promise<ChatResponseV2> {
  return postV2('/api/chat/v2/report', payload);
}
