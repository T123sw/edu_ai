import { apiRequest } from "./client";
import type {
  StandardResourceBatch,
  StandardResourceCatalog,
} from "./types";

function coursePath(courseId: string) {
  return `/api/courses/${encodeURIComponent(courseId)}`;
}

export function getStandardResources(courseId: string) {
  return apiRequest<StandardResourceCatalog>(
    `${coursePath(courseId)}/standard-resources`,
  );
}

export function createStandardResourceBatch(
  courseId: string,
  leafIds: string[],
) {
  return apiRequest<StandardResourceBatch>(
    `${coursePath(courseId)}/standard-resource-batches`,
    {
      method: "POST",
      body: JSON.stringify({ leaf_ids: leafIds }),
    },
  );
}

export function getStandardResourceBatch(courseId: string, batchId: string) {
  return apiRequest<StandardResourceBatch>(
    `${coursePath(courseId)}/standard-resource-batches/${encodeURIComponent(batchId)}`,
  );
}

export function retryStandardResourceBatch(courseId: string, batchId: string) {
  return apiRequest<StandardResourceBatch>(
    `${coursePath(courseId)}/standard-resource-batches/${encodeURIComponent(batchId)}/retry`,
    { method: "POST" },
  );
}

export function reviewStandardResource(
  courseId: string,
  materialId: string,
  decision: "approved" | "rejected",
  reason = "",
) {
  return apiRequest(
    `${coursePath(courseId)}/standard-resources/${encodeURIComponent(materialId)}/review`,
    {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    },
  );
}

export function approvePendingStandardResources(
  courseId: string,
  batchId: string,
) {
  return apiRequest(
    `${coursePath(courseId)}/standard-resource-batches/${encodeURIComponent(batchId)}/approve-pending`,
    { method: "POST" },
  );
}
