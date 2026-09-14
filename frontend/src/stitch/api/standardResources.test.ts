import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import {
  createStandardResourceBatch,
  previewStandardResourceBatch,
  reviewStandardResource,
} from "./standardResources.ts";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function successfulJson(body: unknown = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

test("standard resource preview and creation preserve selected policy", async () => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({
      url: String(input),
      body: JSON.parse(String(init?.body || "{}")) as Record<string, unknown>,
    });
    return successfulJson({});
  };

  await previewStandardResourceBatch(
    "course/一",
    ["leaf-1"],
    ["study_guide"],
    "repair_rejected",
  );
  await createStandardResourceBatch("course/一", ["leaf-1"], {
    standardKinds: ["study_guide"],
    mode: "repair_rejected",
    idempotencyKey: "request-1",
    graphVersion: "graph-v2",
  });

  assert.match(requests[0].url, /course%2F%E4%B8%80\/standard-resource-batches\/preview$/);
  assert.deepEqual(requests[0].body, {
    leaf_ids: ["leaf-1"],
    standard_kinds: ["study_guide"],
    mode: "repair_rejected",
  });
  assert.deepEqual(requests[1].body, {
    leaf_ids: ["leaf-1"],
    standard_kinds: ["study_guide"],
    mode: "repair_rejected",
    idempotency_key: "request-1",
    graph_version: "graph-v2",
  });
});

test("review binds the teacher decision to the previewed version and hash", async () => {
  let body: Record<string, unknown> = {};
  globalThis.fetch = async (_input, init) => {
    body = JSON.parse(String(init?.body || "{}")) as Record<string, unknown>;
    return successfulJson({});
  };

  await reviewStandardResource(
    "course-1",
    "standard-leaf-guide",
    "rejected",
    7,
    "sha256-content-v7",
    "例题边界错误",
  );

  assert.deepEqual(body, {
    decision: "rejected",
    reason: "例题边界错误",
    expected_version: 7,
    expected_content_hash: "sha256-content-v7",
  });
});
