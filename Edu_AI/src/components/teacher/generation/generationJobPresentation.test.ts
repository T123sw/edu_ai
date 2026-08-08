import assert from "node:assert/strict";
import test from "node:test";

import type { JobRecord } from "../../../jobs/types.ts";
import { presentGenerationJob } from "./generationJobPresentation.ts";

function job(overrides: Partial<JobRecord>): JobRecord {
  return {
    schema_version: 2,
    version: 1,
    edu_job_id: "job-1",
    kind: "generate_report",
    status: "succeeded",
    step: "completed",
    progress: 100,
    message: "",
    owner_user_id: "teacher-a",
    scope_type: "course",
    input_summary: { title: "快速排序" },
    retryable: false,
    cancelable: false,
    created_at: "2026-08-08T00:00:00Z",
    updated_at: "2026-08-08T00:01:00Z",
    ...overrides,
  };
}

test("recent generation uses the subject as its title and the matching tool icon", () => {
  assert.deepEqual(presentGenerationJob(job({})), {
    title: "快速排序",
    icon: "article",
    accent: "#b7791f",
  });
  assert.deepEqual(
    presentGenerationJob(job({
      kind: "generate_quiz",
      input_summary: { topic: "冒泡排序" },
    })),
    { title: "冒泡排序", icon: "quiz", accent: "#3157d5" },
  );
});

test("legacy jobs fall back to their resource name without a generation suffix", () => {
  assert.equal(
    presentGenerationJob(job({ input_summary: {} })).title,
    "教学报告",
  );
});
