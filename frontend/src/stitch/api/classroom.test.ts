import assert from "node:assert/strict";
import test from "node:test";

import { buildClassroomListPath } from "./classroomPaths";

test("classroom list requests one explicit personal or course space", () => {
  assert.equal(
    buildClassroomListPath("course 1", "mine"),
    "/api/courses/course%201/classrooms?space=mine",
  );
  assert.equal(
    buildClassroomListPath("course 1", "course"),
    "/api/courses/course%201/classrooms?space=course",
  );
});
