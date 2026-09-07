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

test("course home counts only personal resources", async () => {
  const homeDashboard = await readFile(new URL("./HomeDashboard.tsx", import.meta.url), "utf8");
  assert.match(homeDashboard, /getCourseMaterials\(course\.id,\s*\{\s*space:\s*["']mine["']/u);
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
  assert.equal(card.updatedLabel, "暂无使用记录");
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

test("course usage comes from user visits, never from content modification", () => {
  const facts = { documentCount: 0, resourceCount: 0, activeJobCount: 0, learningOverview: null };
  const visited = { ...courseFixture, last_used_at: "2026-09-07T08:00:00Z" };
  const card = toCourseCardPresentation(visited, facts);
  assert.match(card.updatedLabel, /^最近使用 2026\/9\/7 /);
  assert.equal(toCourseCardPresentation(courseFixture, facts).updatedLabel, "暂无使用记录");
  assert.equal(toCourseCardPresentation({ ...visited, last_used_at: "invalid" }, facts).updatedLabel, "暂无使用记录");
  const previousVisit = { courseId: courseFixture.id, visitedAt: "2026-09-08T08:00:00Z" };
  assert.match(toCourseCardPresentation(visited, facts, "teacher", previousVisit).updatedLabel, /2026\/9\/8/);
  assert.equal(toCourseCardPresentation(courseFixture, facts, "teacher", { ...previousVisit, courseId: "other" }).updatedLabel, "暂无使用记录");
});
