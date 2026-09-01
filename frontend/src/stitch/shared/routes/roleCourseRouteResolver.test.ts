import assert from "node:assert/strict";
import test from "node:test";

import { buildRoleCourseHash, homeHashForRole } from "./roleCourseRouteResolver.ts";

test("role course links preserve the shared page while selecting the correct workspace route", () => {
  assert.equal(
    buildRoleCourseHash("teacher", "learning", "course-1"),
    "#learning?course_id=course-1",
  );
  assert.equal(
    buildRoleCourseHash("student", "learning", "course-1"),
    "#student-learning?course_id=course-1",
  );
  assert.equal(
    buildRoleCourseHash("teacher", "resources", "course 1", { material_type: "report", material_id: "r1" }),
    "#resources?course_id=course+1&material_type=report&material_id=r1",
  );
  assert.equal(
    buildRoleCourseHash("student", "resources", "course 1", { material_type: "report", material_id: "r1" }),
    "#student-resources?course_id=course+1&material_type=report&material_id=r1",
  );
});

test("student course links ignore legacy knowledge views and keep scope values", () => {
  assert.equal(
    buildRoleCourseHash("student", "knowledge", "c1", { view: "documents", scopeType: "knowledge_point", scopeId: "node 1" }),
    "#student-course-knowledge?course_id=c1&scopeType=knowledge_point&scopeId=node+1",
  );
  assert.equal(buildRoleCourseHash("student", "edit", "c1"), "#student-course-detail?course_id=c1");
});

test("role home links return to the correct global workspace", () => {
  assert.equal(homeHashForRole("student"), "#student-home");
  assert.equal(homeHashForRole("teacher"), "#home");
});

test("role course links preserve an exact resource version", () => {
  assert.equal(
    buildRoleCourseHash("student", "resources", "course-1", {
      material_type: "classroom",
      material_id: "classroom-1",
      resource_version: 3,
    }),
    "#student-resources?course_id=course-1&material_type=classroom&material_id=classroom-1&resource_version=3",
  );
});

test("role classroom links forward catalog selection for both workspaces", () => {
  const target = { node_id: "leaf-1", resource_id: "guide-1" };
  assert.equal(
    buildRoleCourseHash("student", "classroom-studio", "course-1", target),
    "#student-classroom?course_id=course-1&node_id=leaf-1&resource_id=guide-1",
  );
  assert.equal(
    buildRoleCourseHash("teacher", "classroom-studio", "course-1", target),
    "#classroom-studio?course_id=course-1&node_id=leaf-1&resource_id=guide-1",
  );
});
