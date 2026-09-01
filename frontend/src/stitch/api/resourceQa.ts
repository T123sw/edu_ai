import { apiBlob, apiRequest } from "./client";
import type {
  ResourceQaKind,
  ResourceQaSession,
  ResourceQaTurnRequest,
  ResourceQaTurnSubmission,
} from "./types";

function resourceQaBasePath(courseId: string, kind: ResourceQaKind, resourceId: string): string {
  return `/api/courses/${encodeURIComponent(courseId)}/resources/${encodeURIComponent(kind)}/${encodeURIComponent(resourceId)}/qa`;
}

export function buildResourceQaSessionPath(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
  resourceVersion: number,
): string {
  return `${resourceQaBasePath(courseId, kind, resourceId)}/session?resource_version=${encodeURIComponent(String(resourceVersion))}`;
}

export function buildResourceQaTurnsPath(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
): string {
  return `${resourceQaBasePath(courseId, kind, resourceId)}/turns`;
}

export function getResourceQaSession(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
  resourceVersion: number,
): Promise<ResourceQaSession> {
  return apiRequest<ResourceQaSession>(
    buildResourceQaSessionPath(courseId, kind, resourceId, resourceVersion),
  );
}

export function submitResourceQaTurn(
  courseId: string,
  kind: ResourceQaKind,
  resourceId: string,
  request: ResourceQaTurnRequest,
): Promise<ResourceQaTurnSubmission> {
  return apiRequest<ResourceQaTurnSubmission>(buildResourceQaTurnsPath(courseId, kind, resourceId), {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function fetchResourceQaAudioBlobUrl(path: string): Promise<string> {
  if (!path.startsWith("/api/")) {
    throw new Error("Resource Q&A audio path must be an authenticated API path");
  }
  const blob = await apiBlob(path);
  return URL.createObjectURL(blob);
}
