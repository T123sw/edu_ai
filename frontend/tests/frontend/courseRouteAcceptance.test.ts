import assert from "node:assert/strict";

import { resolveCourseRouteState } from "../../src/stitch/course/CourseRouteProvider.tsx";
import {
  buildTeacherCourseHash,
  readTeacherCourseId,
} from "../../src/stitch/teacherRoutes.ts";

const copiedHash = buildTeacherCourseHash("knowledge", "course / 中文");
assert.equal(
  readTeacherCourseId(copiedHash),
  "course / 中文",
  "copied course links must round-trip the exact course identity",
);
assert.equal(
  resolveCourseRouteState(copiedHash, "stale-course").courseId,
  "course / 中文",
  "hard refresh must prefer the URL over remembered local state",
);
assert.equal(
  resolveCourseRouteState("#course-detail", "stale-course").courseId,
  null,
  "a course page without an ID must not fall back to stale local state",
);

console.log("course route acceptance frontend tests passed");
