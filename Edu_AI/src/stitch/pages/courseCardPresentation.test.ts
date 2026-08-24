import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

import { toCourseCardPresentation } from "./courseCardPresentation.ts";

const courseFixture = {
  id: "course-physics",
  title: "大学物理",
  description: "力学、电磁学与近代物理",
  membership_role: "editor" as const,
  revision: 4,
  updated_at: "2026-08-06T16:30:00+08:00",
};

const learningOverview = {
  course_id: courseFixture.id,
  pending_tasks: 2,
  in_progress_tasks: 1,
  self_reported_completed_tasks: 0,
  activity_evidenced_completed_tasks: 0,
  assessment_verified_completed_tasks: 0,
  latest_activity_at: null,
};

test("course card presentation contains only factual metrics", () => {
  const card = toCourseCardPresentation(courseFixture, {
    documentCount: 4,
    resourceCount: 7,
    activeJobCount: 1,
    learningOverview,
  }, "teacher");

  assert.equal("progress" in card, false);
  assert.deepEqual(card.metrics, [
    { label: "进行中学习任务", value: 1 },
    { label: "后台生成中", value: 1 },
    { label: "课程资料", value: 4 },
    { label: "个人资源", value: 7 },
  ]);
  assert.equal(card.learningStatusLabel, null);
});

test("course overviews count only personal resources", async () => {
  const courseDetail = await readFile(new URL("./CourseDetail.tsx", import.meta.url), "utf8");
  const homeDashboard = await readFile(new URL("./HomeDashboard.tsx", import.meta.url), "utf8");
  assert.match(courseDetail, /getCourseMaterials\(course\.id,\s*\{\s*space:\s*["']mine["']/u);
  assert.match(homeDashboard, /getCourseMaterials\(course\.id,\s*\{\s*space:\s*["']mine["']/u);
  assert.doesNotMatch(courseDetail, /课程资源|资源管理|课程共享/u);
});

test("course card omits developer-facing permission and revision fields", () => {
  const card = toCourseCardPresentation(courseFixture, {
    documentCount: 0,
    resourceCount: 0,
    activeJobCount: 0,
    learningOverview: null,
  });
  assert.equal("roleLabel" in card, false);
  assert.equal("revisionLabel" in card, false);
  assert.match(card.updatedLabel, /^最近更新 /);
  assert.equal(card.metrics[0]?.value, "—");
  assert.equal(card.learningStatusLabel, "学习任务暂不可用");
});

test("student course card prioritizes pending learning", () => {
  const card = toCourseCardPresentation(courseFixture, {
    documentCount: 4,
    resourceCount: 7,
    activeJobCount: 3,
    learningOverview,
  }, "student");

  assert.deepEqual(card.metrics.slice(0, 2), [
    { label: "待学习任务", value: 2 },
    { label: "后台生成中", value: 3 },
  ]);
});
