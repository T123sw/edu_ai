// 教师工具相关 API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface LessonPlanStep {
  step: string;
  content: string;
  duration: string;
}

export interface LessonPlan {
  title: string;
  objectives: string[];
  keyPoints: string[];
  hardPoints: string[];
  process: LessonPlanStep[];
  homework: string;
}

export interface LessonPlanRequest {
  courseName: string;
  duration?: number;
  knowledgePoints?: string[];
  difficulty?: 'low' | 'medium' | 'high';
  keyPoints?: string;
  hardPoints?: string;
}

export interface LessonPlanMeta {
  id: string;
  title: string;
  topic: string;
  difficulty: string;
  knowledge_points: string[];
  created_at: string;
  updated_at: string;
}

export interface LessonPlanRecord extends LessonPlanMeta {
  plan: LessonPlan;
}

export interface Question {
  id: number;
  type: string;
  difficulty: string;
  content: string;
  options?: string[] | null;
  answer?: string | null;
  analysis?: string | null;
}

export interface QuestionGenerateRequest {
  knowledgePoints?: string[];
  types?: string[];
  difficulty?: 'low' | 'medium' | 'high';
  count?: number;
}

export async function generateLessonPlan(payload: LessonPlanRequest): Promise<LessonPlan> {
  const body = {
    course_name: payload.courseName,
    duration: payload.duration ?? 45,
    knowledge_points: payload.knowledgePoints ?? [],
    difficulty: payload.difficulty ?? 'medium',
    key_points: payload.keyPoints,
    hard_points: payload.hardPoints,
  };

  const response = await fetch(`${API_BASE_URL}/teacher/lesson_plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '生成教案失败' }));
    throw new Error(error.detail || `生成教案失败: ${response.statusText}`);
  }

  return (await response.json()) as LessonPlan;
}

export async function suggestKnowledgePoints(courseName: string): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/teacher/knowledge_points`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ course_name: courseName }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '生成知识点失败' }));
    throw new Error(error.detail || `生成知识点失败: ${response.statusText}`);
  }

  const data = await response.json();
  return (data.knowledge_points || []) as string[];
}

export async function listLessonPlans(): Promise<LessonPlanMeta[]> {
  const response = await fetch(`${API_BASE_URL}/teacher/lesson_plans`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取教案列表失败' }));
    throw new Error(error.detail || `获取教案列表失败: ${response.statusText}`);
  }

  const data = await response.json();
  return (data.plans || []) as LessonPlanMeta[];
}

export async function getLessonPlanDetails(id: string): Promise<LessonPlan> {
  const response = await fetch(`${API_BASE_URL}/teacher/lesson_plans/${id}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '获取教案详情失败' }));
    throw new Error(error.detail || `获取教案详情失败: ${response.statusText}`);
  }

  return (await response.json()) as LessonPlan;
}

export async function deleteLessonPlan(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/teacher/lesson_plans/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '删除教案失败' }));
    throw new Error(error.detail || `删除教案失败: ${response.statusText}`);
  }
}

export async function generateQuestions(payload: QuestionGenerateRequest): Promise<Question[]> {
  const body = {
    knowledge_points: payload.knowledgePoints ?? [],
    types: payload.types ?? [],
    difficulty: payload.difficulty ?? 'medium',
    count: payload.count ?? 10,
  };

  const response = await fetch(`${API_BASE_URL}/teacher/questions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '生成题目失败' }));
    throw new Error(error.detail || `生成题目失败: ${response.statusText}`);
  }

  const data = await response.json();
  return (data.questions || []) as Question[];
}

