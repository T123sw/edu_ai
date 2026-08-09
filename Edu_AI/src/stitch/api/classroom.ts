import { API_BASE_URL, apiBlob, apiRequest } from "./client";
import type { ClassroomMaterial, EduJob } from "./types";
import {
  buildClassroomListPath,
  type ClassroomSpace,
} from "./classroomPaths";

const AUTH_STORAGE_KEY = "edu-ai-auth";

export function generateClassroom(
  courseId: string,
  payload: {
    requirement: string;
    topic?: string;
    audience?: string;
    objectives?: string[];
    scene_count?: number;
    duration_minutes?: number;
    teaching_style?: string;
    source_mode?: "course_auto" | "selected_documents" | "none";
    selected_doc_ids?: string[];
    enable_web_search?: boolean;
    enable_tts?: boolean;
    voice?: string;
    idempotency_key?: string;
  },
) {
  return apiRequest<EduJob>(`/api/courses/${courseId}/classrooms/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJobStatus(eduJobId: string) {
  return apiRequest<EduJob>(`/api/jobs/${eduJobId}`);
}

export function listClassrooms(
  courseId: string,
  space: ClassroomSpace,
) {
  return apiRequest<ClassroomMaterial[]>(
    buildClassroomListPath(courseId, space),
  );
}

export function exportClassroomVideo(courseId: string, classroomId: string) {
  return apiRequest<EduJob>(
    `/api/courses/${encodeURIComponent(courseId)}/classrooms/${encodeURIComponent(classroomId)}/video/export`,
    { method: "POST" },
  );
}

export function downloadClassroomVideoArtifact(path: string) {
  return apiBlob(path);
}

function readAuthToken() {
  if (typeof window === "undefined") return "";
  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) return "";
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || "";
  } catch {
    return "";
  }
}

/**
 * 课件配音文件路由要求登录（跟其他 material 路由一致），`<audio>`/`new
 * Audio()` 标签发不出 Authorization 头——所以跟课堂播放器里
 * `fetchAuthenticatedBlobUrl` 同样的做法：带 token 手动 fetch 一次，转成
 * blob object URL 再交给播放器，而不是直接把后端相对路径塞给 `<audio src>`。
 */
async function fetchAuthenticatedAudioBlobUrl(relativeUrl: string): Promise<string> {
  const headers = new Headers();
  const token = readAuthToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}${relativeUrl}`, { headers });
  if (!response.ok) throw new Error(`Failed to load classroom audio: ${response.status}`);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

/** 就地把 scenes 里 speech action 的相对 audioUrl（后端迁移落盘后的
 * `/api/courses/.../audio/...` 路径）换成带 auth 的 blob object URL，
 * 播放器（ActionEngine）本身不需要知道任何鉴权细节。没有 audioUrl 或已经
 * 是 blob:/http(s): 的跳过——幂等，可以对同一个 material 反复调用。 */
async function resolveClassroomAudioUrls(material: ClassroomMaterial): Promise<void> {
  const tasks: Promise<void>[] = [];
  for (const scene of material.scenes ?? []) {
    for (const action of scene.actions ?? []) {
      const audioUrl = (action as { audioUrl?: unknown }).audioUrl;
      if (typeof audioUrl !== "string" || !audioUrl.startsWith("/")) continue;
      tasks.push(
        fetchAuthenticatedAudioBlobUrl(audioUrl)
          .then((blobUrl) => {
            (action as { audioUrl?: string }).audioUrl = blobUrl;
          })
          .catch(() => {
            // 配音文件取不到就保持原样，actionEngine 的三级兜底会接住
            // （tier-1 audio.play() 失败 -> resolve，不会卡住播放）。
          }),
      );
    }
  }
  await Promise.all(tasks);
}

export async function getClassroom(courseId: string, classroomId: string) {
  const material = await apiRequest<ClassroomMaterial>(`/api/courses/${courseId}/classrooms/${classroomId}`);
  await resolveClassroomAudioUrls(material);
  return material;
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
