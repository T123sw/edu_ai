import assert from "node:assert/strict";
import test from "node:test";

import { resolveCourseRouteState } from "./CourseRouteProvider.tsx";
import { canCourse } from "./coursePermissions.ts";

test("URL course wins over remembered course", () => {
  assert.equal(
    resolveCourseRouteState("#ai?course_id=course-b", "course-a").courseId,
    "course-b",
  );
});

test("student course routes provide the same course context", () => {
  assert.equal(
    resolveCourseRouteState("#student-ai?course_id=course-b", "course-a").courseId,
    "course-b",
  );
  assert.equal(
    resolveCourseRouteState("#student-course-knowledge?course_id=course-c", null).courseId,
    "course-c",
  );
});

test("remembered course is only a home-page convenience", () => {
  assert.equal(resolveCourseRouteState("#home", "course-a").courseId, "course-a");
  assert.equal(resolveCourseRouteState("#course-detail", "course-a").courseId, null);
});

test("malformed route values never become a course identity", () => {
  assert.equal(resolveCourseRouteState("#ai?course_id=undefined", "course-a").courseId, null);
  assert.equal(resolveCourseRouteState("#ai?course_id=%20", "course-a").courseId, null);
});

test("viewer is read-only while editors and owners can mutate", () => {
  assert.equal(canCourse("viewer", "read"), true);
  assert.equal(canCourse("viewer", "edit"), false);
  assert.equal(canCourse("viewer", "generate"), false);
  assert.equal(canCourse("editor", "manage_resources"), true);
  assert.equal(canCourse("owner", "manage_members"), true);
});
