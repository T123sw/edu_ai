import assert from "node:assert/strict";
import test from "node:test";

import {
  TEACHER_STUDIO_ACTIONS,
  TEACHER_STUDIO_ACTION_ORDER,
} from "./studioActions.ts";

test("generation studio exposes all eight approved resource entries in order", () => {
  const expectedOrder = [
    "report",
    "lesson_plan",
    "blog",
    "quiz",
    "ppt",
    "flashcard",
    "graph",
    "game",
  ];

  assert.deepEqual(TEACHER_STUDIO_ACTION_ORDER, expectedOrder);
  assert.deepEqual(
    TEACHER_STUDIO_ACTIONS.map((action) => action.type),
    expectedOrder,
  );
  assert.equal(new Set(TEACHER_STUDIO_ACTION_ORDER).size, 8);
});

test("every generation entry has visible user-facing copy and a stable accent", () => {
  for (const action of TEACHER_STUDIO_ACTIONS) {
    assert.ok(action.title.trim(), `${action.type} should have a title`);
    assert.ok(action.description.trim(), `${action.type} should have a description`);
    assert.match(action.color, /^#[0-9a-f]{6}$/i);
  }
});
