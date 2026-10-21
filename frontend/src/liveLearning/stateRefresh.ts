import { apiRequest } from '../stitch/api/client';
import type { JobListResponse } from '../jobs/types';
import type { Classroom, LearningState } from '../selfLearning/model';
import type { LearningJob } from './TaskCenter';

export type LiveLearningState = LearningState & { shared: Classroom[]; serverJobs: LearningJob[] };

export async function refreshLearningState(snapshot: LiveLearningState, activeId: string, request = apiRequest): Promise<LiveLearningState> {
  if (!snapshot.rooms.some(room => room.id === activeId)) {
    return request<LiveLearningState>('/api/self-learning/state');
  }
  // A classroom refresh needs one course, not the full contents of every course
  // in the account. Keep the global task launcher current via its own ledger.
  const [room, jobs] = await Promise.all([
    request<Classroom>(`/api/self-learning/courses/${encodeURIComponent(activeId)}`),
    request<JobListResponse>('/api/jobs?limit=100'),
  ]);
  return { ...snapshot, rooms: snapshot.rooms.map(previous => previous.id === activeId ? room : previous),
    serverJobs: jobs.items.map(job => ({ edu_job_id: job.edu_job_id, status: job.status, kind: job.kind,
      created_at: job.created_at,
      progress: job.progress ?? undefined, message: job.message ?? undefined, course_id: job.course_id ?? undefined,
      retryable: job.retryable, error_message: job.error_message ?? undefined })) };
}
