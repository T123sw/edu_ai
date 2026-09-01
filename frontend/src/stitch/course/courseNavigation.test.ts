import assert from "node:assert/strict";
import test from "node:test";

import {
  getCourseNavigation,
  getCoursePageTitle,
  isCourseWorkspaceRoute,
} from "./courseNavigation.ts";

test("course workbar exposes the approved destinations in order", () => {
  assert.deepEqual(
    getCourseNavigation().map(({ id, label }) => [id, label]),
    [
      ["workspace", "工作台"],
      ["knowledge", "课程知识"],
      ["classroom", "AI课堂"],
      ["resources", "资源管理"],
      ["learning", "学习任务"],
    ],
  );
});

test("overview and settings stay routable without occupying the workbar", () => {
  const ids = getCourseNavigation().map((item) => item.id);
  assert.equal(ids.includes("overview"), false);
  assert.equal(ids.includes("settings"), false);
  assert.equal(getCoursePageTitle("course-detail"), "课程概览");
  assert.equal(getCoursePageTitle("edit"), "课程设置");
  assert.equal(isCourseWorkspaceRoute("course-detail"), true);
  assert.equal(isCourseWorkspaceRoute("edit"), true);
});

test("knowledge graph deep links belong to course knowledge", () => {
  const knowledge = getCourseNavigation().find((item) => item.id === "knowledge");
  assert.deepEqual(knowledge?.routes, ["knowledge", "graph"]);
});
