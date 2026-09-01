import assert from "node:assert/strict";
import test from "node:test";

import {
  applyPublicationResult,
  applyPublicationWithdrawal,
  getMaterialPublicationPresentation,
} from "./courseResourceSpaces.ts";
import type {
  CourseMaterial,
  MaterialPublicationResponse,
} from "./types.ts";

const privateV1: CourseMaterial = {
  material_id: "draft-1",
  material_type: "report",
  course_id: "course-1",
  owner_user_id: "teacher-a",
  visibility: "private",
  version: 1,
  title: "个人报告",
};

test("private unpublished material offers publish to course", () => {
  assert.deepEqual(
    getMaterialPublicationPresentation(privateV1, "editor"),
    {
      visibilityLabel: "仅自己可见",
      primaryAction: "publish",
      primaryLabel: "发布到课程",
      canWithdraw: false,
    },
  );
});

test("changed private material offers update publication", () => {
  const presentation = getMaterialPublicationPresentation(
    {
      ...privateV1,
      version: 3,
      published_material_id: "published-1",
      published_version: 2,
    },
    "owner",
  );

  assert.equal(presentation.primaryAction, "update");
  assert.equal(presentation.primaryLabel, "更新发布");
});

test("unchanged published private material reports published without another action", () => {
  const presentation = getMaterialPublicationPresentation(
    {
      ...privateV1,
      version: 2,
      published_material_id: "published-1",
      published_version: 2,
    },
    "editor",
  );

  assert.equal(presentation.primaryAction, null);
  assert.equal(presentation.primaryLabel, "已发布");
});

test("viewer never receives publication or course management actions", () => {
  const privatePresentation = getMaterialPublicationPresentation(
    privateV1,
    "viewer",
  );
  const sharedPresentation = getMaterialPublicationPresentation(
    { ...privateV1, visibility: "course", owner_user_id: null },
    "viewer",
  );

  assert.equal(privatePresentation.primaryAction, null);
  assert.equal(privatePresentation.primaryLabel, null);
  assert.equal(sharedPresentation.canWithdraw, false);
});

test("course material is labelled shared and manageable by teachers", () => {
  const presentation = getMaterialPublicationPresentation(
    {
      ...privateV1,
      material_id: "published-1",
      visibility: "course",
      owner_user_id: null,
      published_from_owner_user_id: "teacher-a",
    },
    "editor",
  );

  assert.equal(presentation.visibilityLabel, "课程共享");
  assert.equal(presentation.primaryAction, null);
  assert.equal(presentation.canWithdraw, true);
});

test("applying a publication keeps the private source and upserts the shared snapshot", () => {
  const existingShared: CourseMaterial = {
    ...privateV1,
    material_id: "published-old",
    visibility: "course",
    owner_user_id: null,
  };
  const result: MaterialPublicationResponse = {
    action: "published",
    source_material_id: "draft-1",
    material: {
      ...privateV1,
      material_id: "published-1",
      visibility: "course",
      owner_user_id: null,
      published_from_version: 1,
    },
  };

  const next = applyPublicationResult(
    [privateV1],
    [existingShared],
    result,
  );

  assert.equal(next.personal.length, 1);
  assert.equal(next.personal[0].material_id, "draft-1");
  assert.equal(next.personal[0].published_material_id, "published-1");
  assert.deepEqual(
    next.shared.map((material) => material.material_id),
    ["published-1", "published-old"],
  );
});

test("withdrawing a course snapshot keeps its personal source and clears publication state", () => {
  const personalSource: CourseMaterial = {
    ...privateV1,
    published_material_id: "published-1",
    published_version: 1,
    published_at: "2026-08-07T10:00:00Z",
  };
  const sharedSnapshot: CourseMaterial = {
    ...privateV1,
    material_id: "published-1",
    visibility: "course",
    owner_user_id: null,
    published_from_material_id: "draft-1",
  };

  const next = applyPublicationWithdrawal(
    [personalSource],
    [sharedSnapshot],
    sharedSnapshot,
  );

  assert.equal(next.personal.length, 1);
  assert.equal(next.personal[0].material_id, "draft-1");
  assert.equal(next.personal[0].published_material_id, null);
  assert.equal(next.personal[0].published_version, null);
  assert.deepEqual(next.shared, []);
});
