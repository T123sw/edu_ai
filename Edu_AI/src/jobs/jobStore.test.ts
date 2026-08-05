import assert from "node:assert/strict";
import test from "node:test";
import { createJobStore } from "./jobStore.ts";
import type { JobRecord } from "./types.ts";

function job(
  id: string,
  status: JobRecord["status"],
  updatedAt: string,
  overrides: Partial<JobRecord> = {},
): JobRecord {
  return {
    schema_version: 2,
    version: 1,
    edu_job_id: id,
    kind: "generate_classroom",
    status,
    step: status,
    progress: status === "succeeded" ? 100 : 20,
    message: status,
    owner_user_id: "teacher",
    course_id: "course-1",
    scope_type: "course",
    input_summary: { title: id },
    result_ref: null,
    retryable: status === "failed",
    cancelable: status === "queued" || status === "running",
    created_at: updatedAt,
    updated_at: updatedAt,
    ...overrides,
  };
}

test("hydrates active and recent tasks into one deduplicated newest-first list", () => {
  const store = createJobStore();
  store.getState().mergeJobs([
    job("old", "failed", "2026-08-06T10:00:00Z"),
    job("active", "running", "2026-08-06T11:00:00Z"),
    job("active", "running", "2026-08-06T12:00:00Z", { progress: 60 }),
  ]);

  const state = store.getState();
  assert.deepEqual(state.orderedIds, ["active", "old"]);
  assert.equal(state.jobs.active.progress, 60);
  assert.equal(state.activeCount, 1);
});

test("emits a terminal transition exactly once", () => {
  const store = createJobStore();
  store.getState().mergeJobs([job("one", "running", "2026-08-06T10:00:00Z")]);

  const first = store
    .getState()
    .mergeJobs([job("one", "succeeded", "2026-08-06T10:01:00Z")]);
  const duplicate = store
    .getState()
    .mergeJobs([job("one", "succeeded", "2026-08-06T10:01:00Z")]);

  assert.deepEqual(first.map((transition) => transition.job.edu_job_id), ["one"]);
  assert.deepEqual(duplicate, []);
  assert.deepEqual(store.getState().unreadTerminalIds, ["one"]);
});

test("does not notify for terminal history received during initial hydration", () => {
  const store = createJobStore();
  const transitions = store
    .getState()
    .mergeJobs([job("history", "succeeded", "2026-08-06T10:00:00Z")]);

  assert.deepEqual(transitions, []);
  assert.deepEqual(store.getState().unreadTerminalIds, []);
});

test("course selectors keep jobs isolated and reset removes the previous user", () => {
  const store = createJobStore();
  store.getState().mergeJobs([
    job("course-a", "running", "2026-08-06T10:00:00Z"),
    job("course-b", "queued", "2026-08-06T10:01:00Z", {
      course_id: "course-2",
    }),
  ]);

  assert.deepEqual(
    store.getState().jobsForCourse("course-2").map((item) => item.edu_job_id),
    ["course-b"],
  );
  store.getState().reset();
  assert.deepEqual(store.getState().orderedIds, []);
  assert.equal(store.getState().activeCount, 0);
});
