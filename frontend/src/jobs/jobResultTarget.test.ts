import assert from "node:assert/strict";
import test from "node:test";

import { getJobResultHash } from "./jobResultTarget.ts";
import type { JobRecord } from "./types.ts";

function makeJob(overrides: Partial<JobRecord> = {}): JobRecord {
  return {
    schema_version: 2,
    version: 1,
    edu_job_id: "job-1",
    kind: "generate_report",
    status: "succeeded",
    step: "completed",
    progress: 100,
    message: "completed",
    owner_user_id: "teacher-a",
    course_id: "course-a",
    scope_type: "course",
    input_summary: {},
    result_ref: null,
    retryable: false,
    cancelable: false,
    created_at: "2026-08-06T10:00:00Z",
    updated_at: "2026-08-06T10:01:00Z",
    ...overrides,
  };
}

test("builds an exact course material target", () => {
  assert.equal(
    getJobResultHash(
      makeJob({
        result_ref: {
          resource_type: "course_material",
          course_id: "course-a",
          material_type: "report",
          material_id: "report/1",
        },
      }),
    ),
    "#resources?course_id=course-a&material_type=report&material_id=report%2F1",
  );
});

test("keeps classroom results on the classroom player", () => {
  assert.equal(
    getJobResultHash(
      makeJob({
        result_ref: {
          resource_type: "course_material",
          course_id: "course-a",
          material_type: "classroom",
          material_id: "stage-1",
        },
      }),
    ),
    "#classroom-player?course_id=course-a&classroom_id=stage-1",
  );
});

test("does not offer a generic result link without an exact material", () => {
  assert.equal(
    getJobResultHash(
      makeJob({
        result_ref: {
          resource_type: "course_material",
          course_id: "course-a",
        },
      }),
    ),
    null,
  );
});

test("opens classroom video results in their classroom", () => {
  assert.equal(
    getJobResultHash(
      makeJob({
        kind: "render_video",
        result_ref: {
          resource_type: "classroom_video",
          course_id: "course-a",
          classroom_id: "stage-1",
        },
      }),
    ),
    "#classroom-player?course_id=course-a&classroom_id=stage-1",
  );
});
