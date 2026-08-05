import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTeacherCourseHash,
  readTeacherCourseId,
  teacherSidebarItems,
} from "./teacherRoutes.ts";

test("teacher sidebar exposes the approved six destinations in order", () => {
  assert.deepEqual(
    teacherSidebarItems.map(({ route, label }) => [route, label]),
    [
      ["ai", "问答"],
      ["knowledge", "课程知识库"],
      ["graph", "知识图谱"],
      ["classroom-studio", "AI 课堂"],
      ["resources", "课程资源"],
      ["edit", "课程设置"],
    ],
  );
});

test("teacher course hashes carry an encoded course id", () => {
  assert.equal(
    buildTeacherCourseHash("resources", "course / 中文"),
    "#resources?course_id=course+%2F+%E4%B8%AD%E6%96%87",
  );
  assert.equal(
    readTeacherCourseId("#resources?course_id=course+%2F+%E4%B8%AD%E6%96%87"),
    "course / 中文",
  );
});

test("teacher course hashes fall back safely when the course id is unavailable", () => {
  assert.equal(buildTeacherCourseHash("resources", undefined), "#course");
  assert.equal(buildTeacherCourseHash("resources", " undefined "), "#course");
  assert.equal(buildTeacherCourseHash("resources", " null "), "#course");
  assert.equal(buildTeacherCourseHash("resources", "  "), "#course");
  assert.equal(readTeacherCourseId("#resources?course_id=undefined"), null);
});
