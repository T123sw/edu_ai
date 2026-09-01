import assert from "node:assert/strict";
import test from "node:test";
import { buildWorkspaceHash, readWorkspaceTarget } from "./classroomWorkspaceTarget.ts";

test("workspace targets keep catalog and personal classroom identities exclusive", () => {
  assert.deepEqual(
    readWorkspaceTarget("#teacher-classroom-studio?course_id=course-1&node_id=leaf-1&resource_id=guide-1"),
    { kind: "catalog_resource", nodeId: "leaf-1", resourceId: "guide-1" },
  );
  assert.deepEqual(
    readWorkspaceTarget("#teacher-classroom-studio?course_id=course-1&personal_classroom_id=mine-1"),
    { kind: "personal_classroom", classroomId: "mine-1" },
  );
  assert.deepEqual(
    readWorkspaceTarget("#teacher-classroom-studio?course_id=course-1&node_id=leaf-1&resource_id=guide-1&personal_classroom_id=mine-1"),
    { kind: "overview", nodeId: null },
  );
});

test("workspace hashes write only parameters required by the active target", () => {
  assert.equal(
    buildWorkspaceHash("teacher", "course / 一", { kind: "personal_classroom", classroomId: "mine?#" }),
    "#teacher-classroom-studio?course_id=course+%2F+%E4%B8%80&personal_classroom_id=mine%3F%23",
  );
  assert.equal(
    buildWorkspaceHash("student", "course-1", { kind: "catalog_resource", nodeId: "leaf-1", resourceId: "guide-1" }),
    "#student-classroom?course_id=course-1&node_id=leaf-1&resource_id=guide-1",
  );
});
