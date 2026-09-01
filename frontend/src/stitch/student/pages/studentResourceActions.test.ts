import assert from "node:assert/strict";
import test from "node:test";

import {
  getStudentClassroomActions,
  getStudentResourceActions,
  readStudentResourceSpace,
} from "./studentResourceActions";

test("student resource personal space has owner actions but never publication actions", () => {
  assert.deepEqual(getStudentResourceActions("mine"), [
    "preview",
    "download",
    "rename",
    "delete",
    "regenerate",
  ]);
  assert.equal(getStudentResourceActions("mine").includes("publish" as never), false);
  assert.equal(getStudentResourceActions("mine").includes("withdraw" as never), false);
});

test("student resource course space is read-only", () => {
  assert.deepEqual(getStudentResourceActions("course"), ["preview", "download"]);
});

test("student classroom creation and mutation stay in personal space", () => {
  assert.deepEqual(getStudentClassroomActions("mine"), ["create", "play", "rename", "delete"]);
  assert.deepEqual(getStudentClassroomActions("course"), ["play"]);
});

test("student resource space accepts mine or course and rejects combined modes", () => {
  assert.equal(readStudentResourceSpace("#student-resources?space=mine"), "mine");
  assert.equal(readStudentResourceSpace("#student-resources?space=course"), "course");
  assert.equal(readStudentResourceSpace("#student-resources?space=all"), "mine");
  assert.equal(readStudentResourceSpace("#student-resources"), "mine");
});
