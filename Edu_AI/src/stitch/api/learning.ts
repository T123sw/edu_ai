import { apiRequest } from "./client";
import type {
  AssessmentAttempt,
  AssessmentDraft,
  AssessmentDraftUpdatePayload,
  AssessmentFeedback,
  AssessmentAnalytics,
  CourseLearningSummary,
  LearningEventPayload,
  LearningEventResponse,
  LearningOverview,
  LearningTask,
  LearningTaskCreatePayload,
  StudentAssessment,
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
    { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision }) },
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
    { method: "POST" },
  );

export const generateTaskAssessment = (
  courseId: string,
  taskId: string,
  expectedRevision: number,
) => apiRequest<AssessmentDraft>(`${assessmentPath(courseId, taskId)}/generate`, {
  method: "POST",
  body: JSON.stringify({ expected_revision: expectedRevision, difficulty: "medium" }),
});

export const getStudentAssessment = (courseId: string, taskId: string) =>
  apiRequest<StudentAssessment>(assessmentPath(courseId, taskId));

export const listStudentAssessmentAttempts = (courseId: string, taskId: string) =>
  apiRequest<AssessmentAttempt[]>(`${assessmentPath(courseId, taskId)}/attempts`);

export const startStudentAssessmentAttempt = (courseId: string, taskId: string) =>
  apiRequest<AssessmentAttempt>(`${assessmentPath(courseId, taskId)}/attempts`, { method: "POST" });

export const saveStudentAssessmentAnswers = (
  courseId: string,
  taskId: string,
  attemptId: string,
  payload: { expected_revision: number; answers: Record<string, Record<string, unknown>> },
) => apiRequest<AssessmentAttempt>(`${assessmentPath(courseId, taskId)}/attempts/${attemptId}/answers`, {
  method: "PUT",
  body: JSON.stringify(payload),
});

export const submitStudentAssessmentAttempt = (
  courseId: string,
  taskId: string,
  attemptId: string,
  idempotencyKey: string,
) => apiRequest<AssessmentAttempt>(`${assessmentPath(courseId, taskId)}/attempts/${attemptId}/submit`, {
  method: "POST",
  body: JSON.stringify({ idempotency_key: idempotencyKey }),
});

export const getStudentAssessmentFeedback = (courseId: string, taskId: string) =>
  apiRequest<AssessmentFeedback>(`${assessmentPath(courseId, taskId)}/feedback`);

export const revealStudentAssessmentAnswers = (courseId: string, taskId: string) =>
  apiRequest<AssessmentFeedback>(`${assessmentPath(courseId, taskId)}/reveal`, { method: "POST" });

export const getTaskAssessmentAnalytics = (courseId: string, taskId: string) =>
  apiRequest<AssessmentAnalytics>(`${assessmentPath(courseId, taskId)}/analytics`);

export const reviewAssessmentAttempt = (
  courseId: string,
  taskId: string,
  attemptId: string,
  payload: { item_scores: Record<string, number>; reason_code: string; student_comment: string; private_comment: string },
) => apiRequest<AssessmentAttempt>(`${assessmentPath(courseId, taskId)}/attempts/${attemptId}/review`, {
  method: "POST",
  body: JSON.stringify(payload),
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
