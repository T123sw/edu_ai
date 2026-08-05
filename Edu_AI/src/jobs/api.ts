import { apiRequest } from "../stitch/api/client";
import type { JobListResponse, JobRecord, JobStatus } from "./types";

export type ListJobsOptions = {
  statuses?: JobStatus[];
  kinds?: string[];
  courseId?: string;
  activeOnly?: boolean;
  updatedAfter?: string;
  limit?: number;
  cursor?: string;
};

export function listJobs(options: ListJobsOptions = {}) {
  const params = new URLSearchParams();
  options.statuses?.forEach((status) => params.append("status", status));
  options.kinds?.forEach((kind) => params.append("kind", kind));
  if (options.courseId) params.set("course_id", options.courseId);
  if (options.activeOnly) params.set("active_only", "true");
  if (options.updatedAfter) params.set("updated_after", options.updatedAfter);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const query = params.toString();
  return apiRequest<JobListResponse>(`/api/jobs${query ? `?${query}` : ""}`);
}

export function getJob(jobId: string) {
  return apiRequest<JobRecord>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function cancelJob(jobId: string) {
  return apiRequest<JobRecord>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
}

export function retryJob(jobId: string) {
  return apiRequest<JobRecord>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
  });
}
