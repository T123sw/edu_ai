import assert from "node:assert/strict";
import test from "node:test";
import type { ClassroomCatalogResource } from "../../api/types.ts";
import {
  describeCatalogResourceQa,
  describeOverviewQa,
  describePersonalClassroomQa,
  visibleResourceVersion,
} from "./workspaceQaBinding.ts";

function resource(overrides: Partial<ClassroomCatalogResource>): ClassroomCatalogResource {
  return {
    standard_kind: "study_guide",
    material_type: "report",
    material_id: "guide-1",
    review_status: "approved",
    current_version: 4,
    approved_version: 3,
    resource: { material_id: "guide-1", material_type: "report", title: "学习指南" },
    ...overrides,
  };
}

test("overview has no QA target", () => {
  assert.deepEqual(describeOverviewQa(), { key: "overview", status: "empty" });
});

test("role-visible versions isolate static resource bindings", () => {
  const guide = resource({});
  assert.equal(visibleResourceVersion(guide, "learn"), 3);
  assert.equal(visibleResourceVersion(guide, "manage"), 4);
  const student = describeCatalogResourceQa(guide, "learn");
  const teacher = describeCatalogResourceQa(guide, "manage");
  assert.equal(student.kind, "study_guide");
  assert.equal(student.scopeLabel, "已读取完整文档");
  assert.notEqual(student.key, teacher.key);
});

test("practice and classroom expose their complete context scope", () => {
  const practice = describeCatalogResourceQa(resource({ standard_kind: "practice", material_id: "quiz-1" }), "learn");
  const classroom = describeCatalogResourceQa(resource({ standard_kind: "classroom", material_id: "room-1" }), "manage");
  assert.equal(practice.scopeLabel, "已读取完整习题");
  assert.equal(classroom.scopeLabel, "已读取完整课堂");
  assert.equal(classroom.status, "loading");
});

test("personal classroom waits for its playback controller without a resource version", () => {
  const target = describePersonalClassroomQa("mine-1", "我生成的课堂");
  assert.equal(target.status, "loading");
  assert.equal(target.version, null);
  assert.match(target.key, /personal_classroom:mine-1/);
});
