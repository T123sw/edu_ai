import assert from "node:assert/strict";
import test from "node:test";

import { toCourseLearningMetrics } from "./courseLearningOverview.ts";

const overview = {
  course_id: "course-physics",
  pending_tasks: 2,
  in_progress_tasks: 1,
  self_reported_completed_tasks: 0,
  activity_evidenced_completed_tasks: 0,
  assessment_verified_completed_tasks: 0,
  latest_activity_at: null,
};

test("student course card separates pending learning from background jobs", () => {
  assert.deepEqual(toCourseLearningMetrics("student", overview, 3), [
    { label: "待学习任务", value: 2 },
    { label: "后台生成中", value: 3 },
  ]);
});

test("teacher course card shows active learning tasks", () => {
  assert.deepEqual(toCourseLearningMetrics("teacher", overview, 3), [
    { label: "进行中学习任务", value: 1 },
    { label: "后台生成中", value: 3 },
  ]);
});

test("an unavailable overview is not presented as zero learning tasks", () => {
  assert.deepEqual(toCourseLearningMetrics("student", null, 0), [
    { label: "待学习任务", value: "—" },
    { label: "后台生成中", value: 0 },
  ]);
});
