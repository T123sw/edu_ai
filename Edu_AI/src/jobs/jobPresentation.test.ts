import assert from "node:assert/strict";
import test from "node:test";
import { summarizeJobs } from "./jobPresentation.ts";
import type { JobRecord } from "./types.ts";

function terminalJob(
  id: string,
  status: JobRecord["status"],
  startedAt: string,
  finishedAt: string,
): JobRecord {
  return {
    schema_version: 2,
    version: 1,
    edu_job_id: id,
    kind: "generate_report",
    status,
    step: status,
    progress: 100,
    message: status,
    owner_user_id: "teacher",
    scope_type: "course",
    input_summary: {},
    retryable: status === "failed",
    cancelable: false,
    created_at: startedAt,
    started_at: startedAt,
    finished_at: finishedAt,
    updated_at: finishedAt,
  };
}

test("summarizeJobs reports terminal failure rate and average processing time", () => {
  const summary = summarizeJobs([
    terminalJob(
      "success",
      "succeeded",
      "2026-08-06T10:00:00.000Z",
      "2026-08-06T10:00:02.000Z",
    ),
    terminalJob(
      "failed",
      "failed",
      "2026-08-06T10:01:00.000Z",
      "2026-08-06T10:01:04.000Z",
    ),
    terminalJob(
      "partial",
      "partially_succeeded",
      "2026-08-06T10:02:00.000Z",
      "2026-08-06T10:02:03.000Z",
    ),
  ]);

  assert.deepEqual(summary, {
    completedCount: 3,
    failureCount: 2,
    failureRate: 67,
    averageDurationMs: 3000,
  });
});

test("summarizeJobs excludes canceled and active jobs from quality metrics", () => {
  const summary = summarizeJobs([
    terminalJob(
      "canceled",
      "canceled",
      "2026-08-06T10:00:00.000Z",
      "2026-08-06T10:00:09.000Z",
    ),
    {
      ...terminalJob(
        "running",
        "running",
        "2026-08-06T10:01:00.000Z",
        "2026-08-06T10:01:03.000Z",
      ),
      finished_at: null,
    },
  ]);

  assert.deepEqual(summary, {
    completedCount: 0,
    failureCount: 0,
    failureRate: 0,
    averageDurationMs: 0,
  });
});
