import { apiBlob, apiRequest } from './client';
import type {
  ClassroomQaSession,
  ClassroomQaTurnRequest,
  ClassroomQaTurnSubmission,
} from './types';

function classroomQaBasePath(courseId: string, classroomId: string): string {
  return `/api/courses/${encodeURIComponent(courseId)}/classrooms/${encodeURIComponent(classroomId)}/qa`;
}

export function buildClassroomQaSessionPath(
  courseId: string,
  classroomId: string,
): string {
  return `${classroomQaBasePath(courseId, classroomId)}/session`;
}

export function buildClassroomQaTurnsPath(
  courseId: string,
  classroomId: string,
): string {
  return `${classroomQaBasePath(courseId, classroomId)}/turns`;
}

export function getClassroomQaSession(
  courseId: string,
  classroomId: string,
): Promise<ClassroomQaSession> {
  return apiRequest<ClassroomQaSession>(
    buildClassroomQaSessionPath(courseId, classroomId),
  );
}

export function submitClassroomQaTurn(
  courseId: string,
  classroomId: string,
  request: ClassroomQaTurnRequest,
): Promise<ClassroomQaTurnSubmission> {
  return apiRequest<ClassroomQaTurnSubmission>(
    buildClassroomQaTurnsPath(courseId, classroomId),
    {
      method: 'POST',
      body: JSON.stringify(request),
    },
  );
}

export async function fetchClassroomQaAudioBlobUrl(path: string): Promise<string> {
  if (!path.startsWith('/api/')) {
    throw new Error('Classroom Q&A audio path must be an authenticated API path');
  }
  const blob = await apiBlob(path);
  return URL.createObjectURL(blob);
}
