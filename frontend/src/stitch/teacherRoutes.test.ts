import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTeacherCourseHash,
  readTeacherCourseLocation,
  readTeacherCourseId,
  teacherSidebarItems,
} from "./teacherRoutes.ts";

test("teacher sidebar exposes the approved learning destinations in order", () => {
  assert.deepEqual(
    teacherSidebarItems.map(({ route, label }) => [route, label]),
    [
      ["course-detail", "课程概览"],
      ["learning", "学习任务"],
      ["ai", "问答与生成"],
      ["knowledge", "课程知识"],
      ["classroom-studio", "AI 课堂"],
      ["resources", "个人资源"],
      ["edit", "课程设置"],
    ],
  );
});

test("teacher course hashes carry an encoded course id", () => {
  assert.equal(
    buildTeacherCourseHash("learning", "course-1"),
    "#learning?course_id=course-1",
  );
  assert.equal(
    buildTeacherCourseHash("course-detail", "course / 中文"),
    "#course-detail?course_id=course+%2F+%E4%B8%AD%E6%96%87",
  );
  assert.equal(
    buildTeacherCourseHash("resources", "course / 中文"),
    "#resources?course_id=course+%2F+%E4%B8%AD%E6%96%87",
  );
  assert.equal(
    readTeacherCourseId("#resources?course_id=course+%2F+%E4%B8%AD%E6%96%87"),
    "course / 中文",
  );
});

test("course knowledge links keep identity and ignore legacy view parameters", () => {
  assert.equal(
    buildTeacherCourseHash("knowledge", "c1"),
    "#knowledge?course_id=c1",
  );
  assert.deepEqual(
    readTeacherCourseLocation("#knowledge?course_id=c1&view=structure"),
    { route: "knowledge", courseId: "c1" },
  );
});

test("teacher course hashes carry an exact generated material target", () => {
  assert.equal(
    buildTeacherCourseHash("resources", "course / 中文", {
      material_type: "report",
      material_id: "报告/1",
    }),
    "#resources?course_id=course+%2F+%E4%B8%AD%E6%96%87&material_type=report&material_id=%E6%8A%A5%E5%91%8A%2F1",
  );
});

test("teacher course hashes fall back safely when the course id is unavailable", () => {
  assert.equal(buildTeacherCourseHash("resources", undefined), "#course");
  assert.equal(buildTeacherCourseHash("resources", " undefined "), "#course");
  assert.equal(buildTeacherCourseHash("resources", " null "), "#course");
  assert.equal(buildTeacherCourseHash("resources", "  "), "#course");
  assert.equal(readTeacherCourseId("#resources?course_id=undefined"), null);
});
