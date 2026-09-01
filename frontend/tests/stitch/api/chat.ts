import { apiRequest } from "./client";
import type {
  ChatReplyRequestV2,
  ChatResponseV2,
  KnowledgePointsResponse,
  LessonPlanResponse,
  QuestionGenerateResponse,
  QuizResponse,
  ReportResponse,
} from "./types";

export function sendChatReply(payload: ChatReplyRequestV2) {
  return apiRequest<ChatResponseV2>("/api/chat/v2/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateLessonPlan(payload: {
  topic: string;
  course_id?: string | null;
  selected_doc_ids: string[];
  duration?: number;
  difficulty?: string;
  knowledge_points?: string[];
  key_points?: string | null;
  hard_points?: string | null;
}) {
  return apiRequest<LessonPlanResponse>("/teacher/lesson_plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateTeacherReport(payload: {
  title?: string | null;
  course_id?: string | null;
  selected_doc_ids: string[];
  focus_areas?: string[];
}) {
  return apiRequest<ReportResponse>("/teacher/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateQuiz(payload: {
  title?: string | null;
  course_id?: string | null;
  selected_doc_ids: string[];
  question_type?: string;
  count?: number;
  difficulty?: string;
}) {
  return apiRequest<QuizResponse>("/teacher/quiz", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateKnowledgePoints(payload: { course_name: string }) {
  return apiRequest<KnowledgePointsResponse>("/teacher/knowledge_points", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateQuestions(payload: {
  knowledge_points?: string[];
  types?: string[];
  difficulty?: string;
  count?: number;
}) {
  return apiRequest<QuestionGenerateResponse>("/teacher/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
