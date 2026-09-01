import { apiRequest } from './client';
import type {
  QuizAnswers,
  ResourceLearningAnalytics,
  ResourceLearningEventPayload,
  ResourceLearningProgress,
  ResourceLearningSession,
} from './types';


const base = (courseId: string, resourceId: string, version: number) =>
  `/api/courses/${encodeURIComponent(courseId)}/resources/${encodeURIComponent(resourceId)}/versions/${version}/learning`;

export const getMyResourceLearningProgress = (
  courseId: string,
  resourceId: string,
  version: number,
) => apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/me`);

export const listMyCourseResourceLearningProgress = (courseId: string) =>
  apiRequest<ResourceLearningProgress[]>(
    `/api/courses/${encodeURIComponent(courseId)}/resource-learning/me`,
  );

export const startResourceLearningSession = (
  courseId: string,
  resourceId: string,
  version: number,
) => apiRequest<ResourceLearningSession>(`${base(courseId, resourceId, version)}/sessions`, {
  method: 'POST',
});

export const sendResourceLearningEvents = (
  courseId: string,
  resourceId: string,
  version: number,
  sessionId: string,
  events: ResourceLearningEventPayload[],
) => apiRequest<ResourceLearningProgress>(
  `${base(courseId, resourceId, version)}/sessions/${encodeURIComponent(sessionId)}/events:batch`,
  { method: 'POST', body: JSON.stringify({ events }) },
);

export const submitResourceQuestions = (
  courseId: string,
  resourceId: string,
  version: number,
  idempotencyKey: string,
  answers: QuizAnswers,
) => apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/questions:submit`, {
  method: 'POST',
  body: JSON.stringify({ idempotency_key: idempotencyKey, answers }),
});

export const endResourceLearningSession = (
  courseId: string,
  resourceId: string,
  version: number,
  sessionId: string,
) => apiRequest<ResourceLearningSession>(
  `${base(courseId, resourceId, version)}/sessions/${encodeURIComponent(sessionId)}/end`,
  { method: 'POST' },
);

export const recordReadingActivity = (
  courseId: string,
  resourceId: string,
  version: number,
  payload: {
    event_id: string;
    action: "opened" | "completed";
    occurred_at: string;
  },
) => apiRequest<ResourceLearningProgress>(`${base(courseId, resourceId, version)}/activity`, {
  method: "POST",
  body: JSON.stringify(payload),
});

export const getResourceLearningAnalytics = (
  courseId: string,
  resourceId: string,
  version: number,
) => apiRequest<ResourceLearningAnalytics>(`${base(courseId, resourceId, version)}/analytics`);
