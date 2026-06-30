const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
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

export interface VideoUploadResponse {
  job_id: string;
  status: string;
  message: string;
  saved_video_path: string;
}

export interface VideoJobStatusResponse {
  job_id: string;
  status: string;
  stage: string;
  progress: number;
  message?: string;
  result?: Record<string, any>;
}

export interface VideoSearchRequest {
  query: string;
  top_k?: number;
  course_id?: string;
}

export interface VideoSearchHit {
  id: string;
  score: number;
  transcript: string;
  course_id?: string;
  source_original_path?: string;
  source_chunk_path?: string;
  start_time?: number;
  end_time?: number;
  stream_url?: string;
  playback_url?: string;
}

export interface VideoSearchResponse {
  query: string;
  hits: VideoSearchHit[];
}

export async function uploadVideo(params: {
  file: File;
  courseId: string;
  windowSeconds?: number;
  strideSeconds?: number;
}): Promise<VideoUploadResponse> {
  const { file, courseId, windowSeconds = 30, strideSeconds = 20 } = params;

  const ext = `.${(file.name.split('.').pop() || '').toLowerCase()}`;
  const allowed = ['.mp4', '.mov', '.mkv', '.avi', '.webm'];
  if (!allowed.includes(ext)) {
    throw new Error(`不支持的视频类型: ${ext}，仅支持 ${allowed.join(', ')}`);
  }

  const formData = new FormData();
  formData.append('file', file);

  const query = new URLSearchParams({
    course_id: courseId,
    window_seconds: String(windowSeconds),
    stride_seconds: String(strideSeconds),
  });

  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/video/upload?${query.toString()}`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '上传视频失败' }));
    throw new Error(errorData.detail || `上传视频失败: ${response.statusText}`);
  }

  return (await response.json()) as VideoUploadResponse;
}

export async function getVideoJobStatus(jobId: string): Promise<VideoJobStatusResponse> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/video/jobs/${encodeURIComponent(jobId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取任务状态失败' }));
    throw new Error(errorData.detail || `获取任务状态失败: ${response.statusText}`);
  }

  return (await response.json()) as VideoJobStatusResponse;
}

export async function searchVideoSegments(req: VideoSearchRequest): Promise<VideoSearchResponse> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/video/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '视频检索失败' }));
    throw new Error(errorData.detail || `视频检索失败: ${response.statusText}`);
  }

  return (await response.json()) as VideoSearchResponse;
}
