import { apiRequest } from "./client";
import type {
  AssessmentDraft,
  AssessmentDraftUpdatePayload,
  CourseLearningSummary,
  LearningEventPayload,
  LearningEventResponse,
  LearningOverview,
  LearningTask,
  LearningTaskCreatePayload,
} from "./types";

export const getLearningOverview = (courseId: string) =>
  apiRequest<LearningOverview>(`/api/courses/${courseId}/learning/overview`);

export const listLearningTasks = (courseId: string) =>
  apiRequest<LearningTask[]>(`/api/courses/${courseId}/learning/tasks`);

export const createLearningTask = (
  courseId: string,
  payload: LearningTaskCreatePayload,
) =>
  apiRequest<LearningTask>(`/api/courses/${courseId}/learning/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const publishLearningTask = (courseId: string, taskId: string, expectedRevision: number) =>
  apiRequest<LearningTask>(
    `/api/courses/${courseId}/learning/tasks/${taskId}/publish`,
    { method: "POST" },
  );

const assessmentPath = (courseId: string, taskId: string) =>
  `/api/courses/${courseId}/learning/tasks/${taskId}/assessment`;

export const detectTaskAssessment = (courseId: string, taskId: string) =>
  apiRequest<AssessmentDraft>(`${assessmentPath(courseId, taskId)}/detect`, {
    method: "POST",
  });

export const getTaskAssessmentDraft = (courseId: string, taskId: string) =>
  apiRequest<AssessmentDraft>(`${assessmentPath(courseId, taskId)}/draft`);

export const updateTaskAssessmentDraft = (
  courseId: string,
  taskId: string,
  payload: AssessmentDraftUpdatePayload,
) => apiRequest<AssessmentDraft>(`${assessmentPath(courseId, taskId)}/draft`, {
  method: "PUT",
  body: JSON.stringify(payload),
});

export const validateTaskAssessment = (courseId: string, taskId: string) =>
  apiRequest<AssessmentDraft["quality"]>(
    `${assessmentPath(courseId, taskId)}/validate`,
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision }) },
  );

export const generateTaskAssessment = (
  courseId: string,
  taskId: string,
  expectedRevision: number,
) => apiRequest<AssessmentDraft>(`${assessmentPath(courseId, taskId)}/generate`, {
  method: "POST",
  body: JSON.stringify({ expected_revision: expectedRevision, difficulty: "medium" }),
});

export const recordLearningEvent = (
  courseId: string,
  taskId: string,
  payload: LearningEventPayload,
) =>
  apiRequest<LearningEventResponse>(
    `/api/courses/${courseId}/learning/tasks/${taskId}/events`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const getLearningTaskProgress = (courseId: string, taskId: string) =>
  apiRequest<CourseLearningSummary>(
    `/api/courses/${courseId}/learning/tasks/${taskId}/progress`,
  );
