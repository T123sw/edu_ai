import { apiRequest } from "./client";
import type {
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

export const publishLearningTask = (courseId: string, taskId: string) =>
  apiRequest<LearningTask>(
    `/api/courses/${courseId}/learning/tasks/${taskId}/publish`,
    { method: "POST" },
  );

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
