import { apiRequest } from "./client";
import type {
  StandardResourceBatch,
  StandardResourceBatchPreview,
  StandardResourceCatalog,
  StandardResourceGenerationMode,
  StandardResourceKind,
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
  options: {
    standardKinds: StandardResourceKind[];
    mode: StandardResourceGenerationMode;
    idempotencyKey: string;
    graphVersion: string;
  },
) {
  return apiRequest<StandardResourceBatch>(
    `${coursePath(courseId)}/standard-resource-batches`,
    {
      method: "POST",
      body: JSON.stringify({
        leaf_ids: leafIds,
        standard_kinds: options.standardKinds,
        mode: options.mode,
        idempotency_key: options.idempotencyKey,
        graph_version: options.graphVersion,
      }),
    },
  );
}

export function previewStandardResourceBatch(
  courseId: string,
  leafIds: string[],
  standardKinds: StandardResourceKind[],
  mode: StandardResourceGenerationMode,
) {
  return apiRequest<StandardResourceBatchPreview>(
    `${coursePath(courseId)}/standard-resource-batches/preview`,
    {
      method: "POST",
      body: JSON.stringify({ leaf_ids: leafIds, standard_kinds: standardKinds, mode }),
    },
  );
}

export function listStandardResourceBatches(courseId: string, limit = 10) {
  return apiRequest<StandardResourceBatch[]>(
    `${coursePath(courseId)}/standard-resource-batches?limit=${limit}`,
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
  expectedVersion: number,
  expectedContentHash: string,
  reason = "",
) {
  return apiRequest(
    `${coursePath(courseId)}/standard-resources/${encodeURIComponent(materialId)}/review`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        reason,
        expected_version: expectedVersion,
        expected_content_hash: expectedContentHash,
      }),
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
