import assert from "node:assert/strict";
import test from "node:test";

import { buildJobCourseGroups } from "./jobCourseGrouping.ts";
import type { JobRecord } from "./types.ts";

function job(id: string, courseId?: string | null): JobRecord {
  return {
    schema_version: 2,
    version: 1,
    edu_job_id: id,
    kind: "generate_report",
    status: "succeeded",
    step: "succeeded",
    progress: 100,
    message: "done",
    owner_user_id: "teacher",
    course_id: courseId,
    scope_type: courseId ? "course" : "global",
    input_summary: {},
    retryable: false,
    cancelable: false,
    created_at: "2026-08-11T10:00:00.000Z",
    updated_at: "2026-08-11T10:00:00.000Z",
  };
}

test("course scope only exposes jobs belonging to the course it was opened from", () => {
  const groups = buildJobCourseGroups(
    [job("course-a-new", "course-a"), job("course-b", "course-b"), job("global")],
    {
      currentCourseId: "course-a",
      currentCourseTitle: "计算思维",
      courseTitles: new Map(),
    },
  );

  assert.deepEqual(groups.map((group) => ({
    courseId: group.courseId,
    title: group.title,
    jobIds: group.jobs.map((item) => item.edu_job_id),
  })), [
    {
      courseId: "course-a",
      title: "计算思维",
      jobIds: ["course-a-new"],
    },
  ]);
});

test("global scope groups all jobs by course and leaves unscoped jobs in a final bucket", () => {
  const groups = buildJobCourseGroups(
    [
      job("a-new", "course-a"),
      job("b-new", "course-b"),
      job("a-old", "course-a"),
      job("global"),
    ],
    {
      currentCourseId: null,
      courseTitles: new Map([
        ["course-a", "计算思维"],
        ["course-b", "Python 基础"],
      ]),
    },
  );

  assert.deepEqual(groups.map((group) => ({
    courseId: group.courseId,
    title: group.title,
    jobIds: group.jobs.map((item) => item.edu_job_id),
  })), [
    {
      courseId: "course-a",
      title: "计算思维",
      jobIds: ["a-new", "a-old"],
    },
    {
      courseId: "course-b",
      title: "Python 基础",
      jobIds: ["b-new"],
    },
    {
      courseId: null,
      title: "其他任务",
      jobIds: ["global"],
    },
  ]);
});

test("course scope keeps an empty course group so the drawer can show a scoped empty state", () => {
  const groups = buildJobCourseGroups([job("course-b", "course-b")], {
    currentCourseId: "course-a",
    currentCourseTitle: "计算思维",
    courseTitles: new Map(),
  });

  assert.equal(groups.length, 1);
  assert.equal(groups[0].title, "计算思维");
  assert.deepEqual(groups[0].jobs, []);
});
