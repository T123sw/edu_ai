import assert from "node:assert/strict";
import test from "node:test";

import {
  buildStudentHash,
  readStudentLocation,
} from "./studentRoutes.ts";
import { studentNavigationItems } from "../shell/studentNavigation.ts";

test("student navigation exposes the six approved destinations in order", () => {
  assert.deepEqual(
    studentNavigationItems.map(({ route, label }) => [route, label]),
    [
      ["student-home", "学习首页"],
      ["student-ai", "AI问答"],
      ["student-course-knowledge", "课程知识"],
      ["student-personal-knowledge", "个人知识库"],
      ["student-classroom", "AI课堂"],
      ["student-resources", "资源管理"],
    ],
  );
});

test("course destinations keep course context while personal knowledge remains global", () => {
  assert.equal(
    buildStudentHash("student-course-detail", { courseId: "course-1" }),
    "#student-course-detail?course_id=course-1",
  );
  assert.equal(buildStudentHash("student-ai", { courseId: "course-1" }), "#student-ai?course_id=course-1");
  assert.equal(
    buildStudentHash("student-course-knowledge", { courseId: "course-1", view: "documents" }),
    "#student-course-knowledge?course_id=course-1&view=documents",
  );
  assert.equal(
    buildStudentHash("student-personal-knowledge", { courseId: "course-1" }),
    "#student-personal-knowledge",
  );
  assert.equal(buildStudentHash("student-ai"), "#student-home");
});

test("student location sanitizes course id and applies safe tab defaults", () => {
  assert.deepEqual(readStudentLocation("#student-course-knowledge?course_id=c%201&view=documents"), {
    route: "student-course-knowledge",
    courseId: "c 1",
    view: "documents",
    space: undefined,
  });
  assert.deepEqual(readStudentLocation("#student-resources?course_id=undefined&space=course"), {
    route: "student-resources",
    courseId: null,
    view: undefined,
    space: "course",
  });
  assert.equal(readStudentLocation("#edit?course_id=c1").route, null);
});
