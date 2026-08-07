import assert from "node:assert/strict";
import test from "node:test";

import { toCourseCardPresentation } from "./courseCardPresentation.ts";

const courseFixture = {
  id: "course-physics",
  title: "大学物理",
  description: "力学、电磁学与近代物理",
  membership_role: "editor" as const,
  revision: 4,
  updated_at: "2026-08-06T16:30:00+08:00",
};

test("course card presentation contains only factual metrics", () => {
  const card = toCourseCardPresentation(courseFixture, {
    documentCount: 4,
    resourceCount: 7,
    activeJobCount: 1,
  });

  assert.equal("progress" in card, false);
  assert.deepEqual(card.metrics, [
    { label: "课程资料", value: 4 },
    { label: "课程资源", value: 7 },
    { label: "进行中任务", value: 1 },
  ]);
});

test("course card explains permissions without exposing internal revisions", () => {
  const card = toCourseCardPresentation(courseFixture, {
    documentCount: 0,
    resourceCount: 0,
    activeJobCount: 0,
  });
  assert.equal(card.roleLabel, "可编辑");
  assert.equal("revisionLabel" in card, false);
  assert.match(card.updatedLabel, /^最近更新 /);
});
