import { apiRequest } from "./client";
import type {
  AiLecturerAskResult,
  AiLecturerCourse,
  AiLecturerCourseDetail,
  AiLecturerOfflineTaskCreated,
  AiLecturerOfflineTaskStatus,
  AiLecturerScriptResult,
  ApiEnvelope,
  VideoSearchResponse,
} from "./types";

const AI_LECTURER_BASE_URL = (import.meta.env.VITE_AI_LECTURER_BASE_URL || "http://127.0.0.1:8008").replace(/\/$/, "");

export function searchVideoSegments(query: string, courseId?: string) {
  return apiRequest<VideoSearchResponse>("/api/video/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: 5, course_id: courseId || null }),
  });
}

async function lecturerRequest<T>(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${AI_LECTURER_BASE_URL}${path}`, { ...init, headers });
  const payload = (await response.json()) as ApiEnvelope<T>;

  if (!response.ok || payload.code !== 200) {
    throw new Error(payload.message || "智能讲师接口请求失败");
  }

  return payload.data;
}

export function createAiLecturerCourse(payload: { course_name: string; raw_document: string }) {
  return lecturerRequest<AiLecturerCourse>("/api/v1/online/create_course", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAiLecturerCourse(courseId: string) {
  return lecturerRequest<AiLecturerCourseDetail>(`/api/v1/online/get_course/${courseId}`);
}

export function generateAiLecturerScript(payload: {
  course_title: string;
  current_slide_content: string;
  page_index: number;
  total_pages: number;
}) {
  return lecturerRequest<AiLecturerScriptResult>("/api/v1/online/generate_script", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function speakAiLecturerSentence(payload: { text: string; session_id: number }) {
  return lecturerRequest<Record<string, never> | object>("/api/v1/online/speak_sentence", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function stopAiLecturerSpeaking(sessionId = 0) {
  return lecturerRequest<Record<string, never> | object>("/api/v1/online/stop_speaking", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function askAiLecturer(payload: {
  question: string;
  slide_context: string;
  interrupted_sentence: string;
  session_id: number;
}) {
  return lecturerRequest<AiLecturerAskResult>("/api/v1/online/interrupt_and_ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateAiLecturerFullVideo(payload: {
  course_title: string;
  pages: Array<{ ppt_image_path: string; content_text: string }>;
}) {
  return lecturerRequest<AiLecturerOfflineTaskCreated>("/api/v1/offline/generate_full_video", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAiLecturerTaskStatus(taskId: string) {
  return lecturerRequest<AiLecturerOfflineTaskStatus>(`/api/v1/offline/status/${taskId}`);
}

export function getAiLecturerDownloadUrl(fileName: string) {
  return `${AI_LECTURER_BASE_URL}/api/v1/offline/download/${fileName}`;
}

export function getAiLecturerVideoUrl(path: string) {
  if (!path) return "";
  if (/^https?:\/\//.test(path)) return path;
  return `${AI_LECTURER_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function getAiLecturerOfferUrl() {
  return `${(import.meta.env.VITE_AI_LECTURER_LIVETALKING_URL || "http://127.0.0.1:8010").replace(/\/$/, "")}/offer`;
}

export function getAiLecturerWebRtcUrl() {
  return import.meta.env.VITE_AI_LECTURER_WEBRTC_URL || "http://127.0.0.1:8010/webrtcapi.html";
}
