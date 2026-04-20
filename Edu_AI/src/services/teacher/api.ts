// src/services/teacher/api.ts
import type { ChatInputImageV2, ChatInputVideoV2, StatusCardV2 } from './chatV2';

// 优先使用显式配置；未配置时回退到当前访问源，避免同学访问时落回本机 localhost/127.0.0.1
const BACKEND_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

export interface ChatResponse {
  text: string;
  model?: string;
  sources?: Array<Record<string, any>>;
  conversationId: string;
}

export interface ConversationListItem {
  conversation_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  message_count: number;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
}

export interface ConversationListResponse {
  conversations: ConversationListItem[];
  count: number;
  total?: number;
  limit?: number;
  offset?: number;
  total_messages: number;
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | string;
  content: string;
  timestamp?: string;
  sources?: Array<Record<string, any>>;
  input_images?: ChatInputImageV2[];
  input_videos?: ChatInputVideoV2[];
}

export interface ConversationDetailResponse {
  conversation_id: string;
  title?: string;
  history: ConversationMessage[];
  message_count: number;
  created_at?: string;
  updated_at?: string;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  state?: Record<string, any>;
  status_card?: StatusCardV2 | null;
}

export interface ListChatConversationsOptions {
  courseId?: string;
  scopeType?: 'course' | 'knowledge_point';
  scopeId?: string;
  aggregate?: boolean;
  limit?: number;
  offset?: number;
}

export interface CourseMaterialsQueryOptions {
  materialType?: string;
  scopeType?: 'course' | 'knowledge_point';
  scopeId?: string;
  aggregate?: boolean;
  limit?: number;
  offset?: number;
}

export const sendChatMessage = async (
  message: string,
  _selectedDocIds: string[],
  conversationId?: string | null
): Promise<ChatResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      question: message,
      conversation_id: conversationId || undefined,
      // 当前版本先做纯对话，不传 selectedDocIds；后续可无缝扩展 RAG/工具调用
    }),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`后端请求失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  const data = await resp.json();
  return {
    text: data.answer,
    model: (data as any).model_id,
    sources: (data as any).sources,
    conversationId: (data as any).conversation_id,
  };
};

export interface SseChatRequest {
  question: string;
  conversation_id?: string;
  model_id?: string;
  use_rag?: boolean;
  selected_doc_ids?: string[];
  course_id?: string;
}

export interface SseEventHandlers {
  onMeta?: (meta: Record<string, any>) => void;
  onStatus?: (payload: { stage: string; node?: string }) => void;
  onChunk: (chunk: string) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

const buildSseQuery = (payload: SseChatRequest, token?: string | null) => {
  const params = new URLSearchParams();
  params.set('question', payload.question);
  if (payload.conversation_id) params.set('conversation_id', payload.conversation_id);
  if (payload.model_id) params.set('model_id', payload.model_id);
  if (payload.use_rag) params.set('use_rag', '1');
  if (payload.selected_doc_ids?.length) params.set('selected_doc_ids', payload.selected_doc_ids.join(','));
  if (payload.course_id) params.set('course_id', payload.course_id);
  if (token) params.set('token', token);
  return params.toString();
};

export const startChatStream = (payload: SseChatRequest, handlers: SseEventHandlers) => {
  const token = getAuthToken();
  const url = `${BACKEND_BASE_URL}/api/chat/stream?${buildSseQuery(payload, token)}`;
  const source = new EventSource(url);

  source.addEventListener('meta', (event) => {
    try {
      const data = JSON.parse((event as MessageEvent).data || '{}');
      handlers.onMeta?.(data);
    } catch (err) {
      console.warn('Failed to parse meta event', err);
    }
  });

  source.addEventListener('delta', (event) => {
    try {
      const data = JSON.parse((event as MessageEvent).data || '{}');
      handlers.onChunk(String(data.delta || ''));
    } catch {
      handlers.onChunk((event as MessageEvent).data || '');
    }
  });

  source.addEventListener('status', (event) => {
    try {
      const data = JSON.parse((event as MessageEvent).data || '{}') as { stage?: string; node?: string };
      if (data?.stage) handlers.onStatus?.({ stage: data.stage, node: data.node });
    } catch (err) {
      console.warn('[sse] status parse fail', err);
    }
  });

  source.addEventListener('done', () => {
    handlers.onDone?.();
    source.close();
  });

  source.addEventListener('error', (event) => {
    handlers.onError?.('流式连接断开');
    console.error('SSE error', event);
    source.close();
  });

  return () => source.close();
};

export const listChatConversations = async (
  options?: ListChatConversationsOptions,
): Promise<ConversationListResponse> => {
  const token = getAuthToken();
  const params = new URLSearchParams();

  if (options?.courseId) params.set('course_id', options.courseId);
  if (options?.scopeType) params.set('scope_type', options.scopeType);
  if (options?.scopeId) params.set('scope_id', options.scopeId);
  if (typeof options?.aggregate === 'boolean') params.set('aggregate', options.aggregate ? 'true' : 'false');
  if (typeof options?.limit === 'number') params.set('limit', String(options.limit));
  if (typeof options?.offset === 'number') params.set('offset', String(options.offset));

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/conversations?${params.toString()}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取历史对话列表失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as ConversationListResponse;
};

export const getChatConversationDetail = async (
  conversationId: string
): Promise<ConversationDetailResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/conversations/${conversationId}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取历史对话详情失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as ConversationDetailResponse;
};

export const deleteChatConversation = async (conversationId: string): Promise<void> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`删除历史对话失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

// --------------------- 课程管理接口 ---------------------

export interface BackendCourse {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  objectives?: string[];
  knowledgeGraph?: string;
}

export type BackendCourseCreate = Omit<BackendCourse, 'id'>;

export const fetchCourses = async (): Promise<BackendCourse[]> => {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses`);
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取课程列表失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
  return (await resp.json()) as BackendCourse[];
};

export const fetchCourseDetail = async (courseId: string): Promise<BackendCourse> => {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}`);
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取课程详情失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
  return (await resp.json()) as BackendCourse;
};

export const createCourseBackend = async (course: BackendCourse): Promise<BackendCourse> => {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(course),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`创建课程失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
  return (await resp.json()) as BackendCourse;
};

export const updateCourseDetail = async (course: BackendCourse): Promise<BackendCourse> => {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${course.id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(course),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`更新课程失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
  return (await resp.json()) as BackendCourse;
};

export const deleteCourseBackend = async (courseId: string): Promise<void> => {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}`, {
    method: 'DELETE',
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`删除课程失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

// --------------------- 教案生成接口 ---------------------

export interface LessonPlanRequest {
  topic: string;  // 教学主题（必填）
  course_id?: string;
  selected_doc_ids: string[];  // 选中的文档ID列表（必填）
  duration?: number;  // 课时长度（分钟），默认45
  difficulty?: 'low' | 'medium' | 'high';  // 教学难度，默认medium
  knowledge_points?: string[];  // 知识点标签列表（可选）
  key_points?: string;  // 教学重点（可选）
  hard_points?: string;  // 教学难点（可选）
}

export interface LessonPlanStep {
  step: string;
  content: string;
  duration: string;
}

export interface LessonPlanResponse {
  id?: string;  // 教案ID（后端生成后返回）
  title: string;
  objectives: string[];
  keyPoints: string[];
  hardPoints: string[];
  process: LessonPlanStep[];
  homework: string;
}

export const generateLessonPlan = async (
  request: LessonPlanRequest
): Promise<LessonPlanResponse> => {
  const token = getAuthToken();
  
  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/lesson_plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`生成教案失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as LessonPlanResponse;
};

// --------------------- 报告生成接口 ---------------------

export interface ReportRequest {
  title?: string;  // 报告标题（可选）
  course_id?: string;
  selected_doc_ids: string[];  // 选中的文档ID列表（必填）
  focus_areas?: string[];  // 重点关注领域（可选）
}

export interface ReportSubsection {
  title: string;
  content: string;
}

export interface ReportSection {
  title: string;
  content: string;
  subsections?: ReportSubsection[] | null;
}

export interface ReportResponse {
  id?: string;  // 报告ID（后端生成后返回）
  title: string;
  summary: string;  // 执行摘要
  introduction: string;  // 引言
  mainContent: ReportSection[];  // 主要内容章节
  keyFindings: string[];  // 关键发现
  conclusions: string;  // 结论
  recommendations?: string[] | null;  // 建议（可选）
}

export interface QuizRequest {
  title?: string;
  course_id?: string;
  selected_doc_ids: string[];
  question_type: 'choice' | 'blank' | 'mixed';
  count: number; // 5-20
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface QuizQuestion {
  id: string;
  type: 'choice' | 'blank';
  stem: string;
  options?: string[];
  answer: string;
  explanation: string;
}

export interface QuizResponse {
  id?: string;
  title: string;
  difficulty: 'easy' | 'medium' | 'hard';
  question_type: 'choice' | 'blank' | 'mixed';
  questions: QuizQuestion[];
}

export const generateReport = async (
  request: ReportRequest
): Promise<ReportResponse> => {
  const token = getAuthToken();
  
  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/report`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`生成报告失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as ReportResponse;
};

export const generateQuiz = async (
  request: QuizRequest
): Promise<QuizResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/quiz`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`生成测验失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as QuizResponse;
};

// 获取教案详情
export const getLessonPlanDetail = async (planId: string): Promise<LessonPlanResponse> => {
  const token = getAuthToken();
  
  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/lesson_plans/${planId}`, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取教案详情失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as LessonPlanResponse;
};

// 删除教案
export const deleteLessonPlan = async (planId: string, courseId?: string): Promise<void> => {
  const token = getAuthToken();
  
  const params = new URLSearchParams();
  if (courseId) {
    params.append('course_id', courseId);
  }
  
  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/lesson_plans/${planId}?${params.toString()}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`删除教案失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

// 删除报告
export const deleteReport = async (reportId: string, courseId?: string): Promise<void> => {
  const token = getAuthToken();
  
  const params = new URLSearchParams();
  if (courseId) {
    params.append('course_id', courseId);
  }
  
  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/reports/${reportId}?${params.toString()}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`删除报告失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

export const deleteQuiz = async (quizId: string, courseId?: string): Promise<void> => {
  const token = getAuthToken();

  const params = new URLSearchParams();
  if (courseId) {
    params.append('course_id', courseId);
  }

  const resp = await fetch(`${BACKEND_BASE_URL}/teacher/quizzes/${quizId}?${params.toString()}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`删除测验失败: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

// 获取课程资源列表
export interface CourseMaterialItem {
  id: string;
  name: string;
  type: string;
  addedAt: string;
  courseId?: string;
  scopeType?: 'course' | 'knowledge_point';
  scopeId?: string;
  content?: any;
  isPinned?: boolean;
  pinnedAt?: string;
  version?: Record<string, any>;
  generationState?: Record<string, any>;
  outline?: unknown;
}

export interface CourseMaterialsPageResponse {
  items: CourseMaterialItem[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

export interface PinCourseMaterialRequest {
  is_pinned: boolean;
}

export interface TeachingVideoPptItem {
  material_id: string;
  title: string;
  pptx_url: string;
  html_full_url?: string | null;
  slide_count?: number | null;
  updated_at?: string | null;
}

export interface TeachingVideoTaskResponse {
  task_id: string;
  material_id?: string | null;
  status: string;
  video_url?: string | null;
  error_message?: string | null;
}

export interface AiLectureSessionMaterialResponse {
  material_id: string;
  material_type: string;
  title?: string | null;
  summary?: string | null;
  content?: {
    source_ppt_material_id?: string;
    session_snapshot_id?: string;
    recording_asset_id?: string | null;
    recording_url?: string | null;
    can_continue_interactive?: boolean;
    [key: string]: unknown;
  };
  generation_state?: Record<string, any>;
}

const normalizeCourseMaterialItem = (courseId: string, item: Record<string, any>): CourseMaterialItem => {
  const type = String(item.type || item.material_type || 'unknown');
  let content = item.content;

  if (content === undefined) {
    if (type === 'lesson_plan') {
      content = item.plan;
    } else if (type === 'report') {
      content = item.report;
    } else if (type === 'ppt') {
      content = item.content || item.ppt || item.deck || item;
    } else if (type === 'quiz') {
      content = item.quiz;
    } else if (type === 'blog') {
      content = item.blog ?? item;
    } else {
      content = item;
    }
  }

  return {
    id: String(item.id || item.material_id || ''),
    name: String(item.name || item.title || '未命名'),
    type,
    addedAt: String(item.addedAt || item.created_at || item.updated_at || ''),
    courseId: String(item.courseId || item.course_id || courseId),
    scopeType: String(item.scope_type || item.scopeType || 'course') === 'knowledge_point' ? 'knowledge_point' : 'course',
    scopeId: String(item.scope_id || item.scopeId || '').trim() || undefined,
    content,
    isPinned: Boolean(item.isPinned ?? item.is_pinned),
    pinnedAt:
      typeof item.pinnedAt === 'string'
        ? item.pinnedAt
        : typeof item.pinned_at === 'string'
          ? item.pinned_at
          : undefined,
    version: item.version && typeof item.version === 'object' ? item.version : undefined,
    generationState:
      item.generation_state && typeof item.generation_state === 'object'
        ? item.generation_state
        : item.generationState && typeof item.generationState === 'object'
          ? item.generationState
          : undefined,
    outline: item.outline,
  };
};

export const getCourseMaterials = async (
  courseId: string,
  materialType?: string
): Promise<CourseMaterialItem[]> => {
  const token = getAuthToken();
  
  const params = new URLSearchParams();
  if (materialType) {
    params.append('material_type', materialType);
  }
  
  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/materials?${params.toString()}`, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取课程资源失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  const data = (await resp.json()) as Array<Record<string, any>>;
  return Array.isArray(data) ? data.map((item) => normalizeCourseMaterialItem(courseId, item)) : [];
};

export const getCourseMaterialsPage = async (
  courseId: string,
  options?: CourseMaterialsQueryOptions,
): Promise<CourseMaterialsPageResponse> => {
  const token = getAuthToken();

  const params = new URLSearchParams();
  if (options?.materialType) params.append('material_type', options.materialType);
  if (options?.scopeType) params.append('scope_type', options.scopeType);
  if (options?.scopeId) params.append('scope_id', options.scopeId);
  if (typeof options?.aggregate === 'boolean') params.append('aggregate', options.aggregate ? 'true' : 'false');
  if (typeof options?.limit === 'number') params.append('limit', String(options.limit));
  if (typeof options?.offset === 'number') params.append('offset', String(options.offset));

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/materials?${params.toString()}`, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`閼惧嘲褰囩拠鍓р柤鐠у嫭绨径杈Е: ${resp.status} ${resp.statusText}\n${text}`);
  }

  const data = (await resp.json()) as {
    items?: Array<Record<string, any>>;
    count?: number;
    total?: number;
    limit?: number;
    offset?: number;
  };

  const items = Array.isArray(data.items)
    ? data.items.map((item) => normalizeCourseMaterialItem(courseId, item))
    : [];

  return {
    items,
    count: typeof data.count === 'number' ? data.count : items.length,
    total: typeof data.total === 'number' ? data.total : items.length,
    limit: typeof data.limit === 'number' ? data.limit : items.length,
    offset: typeof data.offset === 'number' ? data.offset : 0,
  };
};

export const deleteCourseMaterial = async (
  courseId: string,
  materialType: string,
  materialId: string,
): Promise<void> => {
  const token = getAuthToken();

  const resp = await fetch(
    `${BACKEND_BASE_URL}/api/courses/${courseId}/materials/${materialType}/${materialId}`,
    {
      method: 'DELETE',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    },
  );

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`鍒犻櫎璇剧▼璧勬簮澶辫触: ${resp.status} ${resp.statusText}\n${text}`);
  }
};

export const pinCourseMaterial = async (
  courseId: string,
  materialType: string,
  materialId: string,
  isPinned: boolean,
): Promise<CourseMaterialItem> => {
  const token = getAuthToken();

  const resp = await fetch(
    `${BACKEND_BASE_URL}/api/courses/${courseId}/materials/${materialType}/${materialId}/pin`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        is_pinned: isPinned,
      } satisfies PinCourseMaterialRequest),
    },
  );

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`缃綅璇剧▼璧勬簮澶辫触: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return normalizeCourseMaterialItem(courseId, (await resp.json()) as Record<string, any>);
};

// 知识图谱相关接口
export interface KnowledgeGraphNode {
  id: string;
  label: string;
  children?: KnowledgeGraphNode[];
  data: {
    level: number;
    summary?: string;
    hasChildren: boolean;
    type: 'concept' | 'example' | 'skill';
  };
}

export interface KnowledgeGraphData {
  root: KnowledgeGraphNode;
}

export const getKnowledgeGraph = async (courseId: string): Promise<KnowledgeGraphData> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/knowledge-graph`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取知识图谱失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as KnowledgeGraphData;
};

export interface BlogGenerateStartRequest {
  course_id: string;
  topic: string;
  selected_doc_ids?: string[];
  top_k?: number;
}

export interface BlogGenerateStartResponse {
  thread_id: string;
}

export interface BlogTaskProgress {
  current_section_idx: number;
  total_sections: number;
}

export interface BlogTaskStatusResponse {
  thread_id: string;
  status: string;
  progress: BlogTaskProgress;
  outline?: Array<Record<string, any>> | null;
  final_markdown?: string | null;
  error_message?: string | null;
}

export interface BlogResumeChaptersRequest {
  chapters: Array<Record<string, any>>;
}

export interface BlogResumeOutlineRequest {
  outline: Array<Record<string, any>>;
}

export const startBlogGenerate = async (
  request: BlogGenerateStartRequest
): Promise<BlogGenerateStartResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/blog/generate/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`启动教学博客生成失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as BlogGenerateStartResponse;
};

export const getBlogTaskStatus = async (
  threadId: string
): Promise<BlogTaskStatusResponse> => {
  const token = getAuthToken();
  if (!token) {
    throw new Error('未登录或登录已过期，请重新登录');
  }

  const resp = await fetch(`${BACKEND_BASE_URL}/api/blog/task/${threadId}/status`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取教学博客任务状态失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as BlogTaskStatusResponse;
};

export const resumeBlogTaskOutline = async (
  threadId: string,
  request: BlogResumeOutlineRequest
): Promise<BlogTaskStatusResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/blog/task/${threadId}/resume-outline`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`恢复教学博客大纲审查失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as BlogTaskStatusResponse;
};

export const resumeBlogTaskChapters = async (
  threadId: string,
  request: BlogResumeChaptersRequest
): Promise<BlogTaskStatusResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/blog/task/${threadId}/resume-chapters`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`恢复教学博客章节审查失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as BlogTaskStatusResponse;
};

export const saveKnowledgeGraph = async (
  courseId: string,
  graphData: KnowledgeGraphData
): Promise<KnowledgeGraphData> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/knowledge-graph`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(graphData),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`保存知识图谱失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as KnowledgeGraphData;
};

export const getTeachingVideoPpts = async (courseId: string): Promise<TeachingVideoPptItem[]> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/teaching-videos/ppts`, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`获取教学视频 PPT 列表失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  const data = (await resp.json()) as Array<Record<string, any>>;
  return Array.isArray(data)
    ? data.map((item) => ({
        material_id: String(item.material_id || ''),
        title: String(item.title || '未命名 PPT'),
        pptx_url: String(item.pptx_url || ''),
        html_full_url: typeof item.html_full_url === 'string' ? item.html_full_url : null,
        slide_count: typeof item.slide_count === 'number' ? item.slide_count : null,
        updated_at: typeof item.updated_at === 'string' ? item.updated_at : null,
      }))
    : [];
};

export const createTeachingVideoTask = async (
  courseId: string,
  payload: { ppt_material_id: string },
): Promise<TeachingVideoTaskResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/teaching-videos`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`创建教学视频任务失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as TeachingVideoTaskResponse;
};

export const createAiLectureSession = async (
  courseId: string,
  payload: { source_ppt_material_id: string; title?: string },
): Promise<AiLectureSessionMaterialResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/lecture-sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`创建 AI 讲解会话失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as AiLectureSessionMaterialResponse;
};

export const getTeachingVideoTaskStatus = async (
  courseId: string,
  taskId: string,
): Promise<TeachingVideoTaskResponse> => {
  const token = getAuthToken();

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/teaching-videos/tasks/${taskId}`, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`查询教学视频任务失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as TeachingVideoTaskResponse;
};
