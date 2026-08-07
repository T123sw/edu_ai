import assert from "node:assert/strict";
import test from "node:test";
import { presentJobError, summarizeJobs } from "./jobPresentation.ts";
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

test("presentJobError maps stable codes to concise Chinese guidance", () => {
  const job = {
    ...terminalJob(
      "source-required",
      "failed",
      "2026-08-06T10:00:00.000Z",
      "2026-08-06T10:00:01.000Z",
    ),
    error_code: "SOURCE_SELECTION_REQUIRED",
    error_message: "selected_doc_ids is required",
  };

  assert.deepEqual(presentJobError(job), {
    title: "没有可用的参考资料",
    detail: "请选择课程知识或个人资料后再试。",
  });
});

test("presentJobError never exposes unknown technical error text", () => {
  const job = {
    ...terminalJob(
      "unknown",
      "failed",
      "2026-08-06T10:00:00.000Z",
      "2026-08-06T10:00:01.000Z",
    ),
    error_code: "VENDOR_INTERNAL_500",
    error_message: "Traceback: provider exploded at internal.py:42",
  };

  const presented = presentJobError(job);

  assert.equal(presented.title, "任务暂时未完成");
  assert.match(presented.detail, /任务 ID：unknown/);
  assert.doesNotMatch(presented.detail, /Traceback|provider|internal\.py/);
});
