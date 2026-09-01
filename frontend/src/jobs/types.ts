export type JobStatus =
  | "queued"
  | "running"
  | "cancel_requested"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "canceled";

export type JobResultRef = {
  resource_type?: string;
  course_id?: string;
  material_type?: string;
  material_id?: string;
  classroom_id?: string;
  scenes_count?: number;
  video_url?: string;
  subtitle_url?: string;
  timeline_url?: string;
  duration_ms?: number;
  scene_count?: number;
  [key: string]: unknown;
};

export type JobRecord = {
  schema_version: number;
  version: number;
  edu_job_id: string;
  kind: string;
  status: JobStatus;
  step: string;
  progress: number;
  message: string;
  owner_user_id: string;
  course_id?: string | null;
  scope_type: string;
  scope_id?: string | null;
  input_summary: Record<string, unknown>;
  result_ref?: JobResultRef | null;
  retry_of_job_id?: string | null;
  parent_job_id?: string | null;
  error_message?: string | null;
  error?: string | null;
  error_code?: string | null;
  retryable: boolean;
  cancelable: boolean;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at: string;
};

export type JobListResponse = {
  items: JobRecord[];
  next_cursor: string | null;
  server_time: string;
};

export const ACTIVE_JOB_STATUSES = new Set<JobStatus>([
  "queued",
  "running",
  "cancel_requested",
]);

export const TERMINAL_JOB_STATUSES = new Set<JobStatus>([
  "succeeded",
  "partially_succeeded",
  "failed",
  "canceled",
]);

export function isActiveJob(job: JobRecord): boolean {
  return ACTIVE_JOB_STATUSES.has(job.status);
}

export function isTerminalJob(job: JobRecord): boolean {
  return TERMINAL_JOB_STATUSES.has(job.status);
}
