import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const shared = readFileSync(new URL("../../src/stitch/shared.tsx", import.meta.url), "utf8");
const courseDetail = readFileSync(new URL("../../src/stitch/pages/CourseDetail.tsx", import.meta.url), "utf8");
const app = readFileSync(new URL("../../src/stitch/App.tsx", import.meta.url), "utf8");

assert.match(shared, /teacherSidebarItems\.map/, "SidebarNav should render the shared teacher navigation contract");
assert.match(
  shared,
  /buildTeacherCourseHash\(item\.route,\s*selectedCourse\?\.id\)/,
  "sidebar links should preserve the selected course in the hash",
);
assert.doesNotMatch(courseDetail, /routes\.video/, "course details must not construct the removed #undefined video route");
assert.match(courseDetail, /buildTeacherCourseHash\(routes\.resources,\s*course\.id\)/, "course details should link to course resources");
assert.match(app, /readTeacherCourseId/, "the app shell should restore course context from the route");
assert.match(app, /getCourse\(routeCourseId\)/, "the app shell should resolve a directly linked course from the backend");

console.log("teacher-navigation-contract tests passed");
