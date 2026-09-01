import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function source(relativePath: string) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

const courseEdit = source("../../src/stitch/pages/CourseEdit.tsx");
const courseDetail = source("../../src/stitch/pages/CourseDetail.tsx");
const graph = source("../../src/stitch/pages/KnowledgeGraph.tsx");
const studio = source("../../src/stitch/pages/ClassroomStudio.tsx");

assert.match(
  courseDetail,
  /buildTeacherCourseHash\(routes\.courseDetail, course\.id\)/,
  "course list links must carry the selected course identity",
);
assert.match(
  courseEdit,
  /canCourse\(courseRole, "edit"\)/,
  "course settings must derive editability from the course role",
);
assert.match(
  courseEdit,
  /canEdit \? \([\s\S]*保存更改[\s\S]*\) : null/,
  "viewer pages must not mount the course save trigger",
);
assert.match(
  courseEdit,
  /!canEdit[\s\S]*课程信息仅供查看/,
  "viewer pages must explain their read-only state",
);
assert.match(
  graph,
  /buildTeacherCourseHash\("ai", courseId/,
  "knowledge graph workspace jumps must preserve course_id",
);
assert.match(
  studio,
  /buildTeacherCourseHash\("course-detail", courseId\)/,
  "classroom studio must return to the current course detail",
);

console.log("course permission rendering frontend tests passed");
