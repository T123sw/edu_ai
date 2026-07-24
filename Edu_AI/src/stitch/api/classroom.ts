import { apiRequest } from "./client";
import type { ClassroomMaterial, EduJob } from "./types";

export function generateClassroom(
  courseId: string,
  payload: { requirement: string; enable_web_search?: boolean },
) {
  return apiRequest<EduJob>(`/api/courses/${courseId}/classrooms/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJobStatus(eduJobId: string) {
  return apiRequest<EduJob>(`/api/jobs/${eduJobId}`);
}

export function getClassroom(courseId: string, classroomId: string) {
  return apiRequest<ClassroomMaterial>(`/api/courses/${courseId}/classrooms/${classroomId}`);
}

/** SPEC-05 §3：sidecar step → 中文文案，跟后端 CLASSROOM_STEP_LABELS 保持一致。 */
export const CLASSROOM_STEP_LABELS: Record<string, string> = {
  queued: "排队中",
  initializing: "初始化",
  researching: "检索资料",
  generating_outlines: "生成大纲",
  generating_scenes: "生成场景",
  generating_media: "生成媒体",
  generating_tts: "合成配音",
  persisting: "保存",
  completed: "完成",
  failed: "失败",
};
