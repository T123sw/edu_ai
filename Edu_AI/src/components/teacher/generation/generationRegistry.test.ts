import assert from "node:assert/strict";
import test from "node:test";

import { generationRegistry } from "./generationRegistry.ts";

test("registry contains exactly nine distinct resources", () => {
  const types = generationRegistry.map((item) => item.resourceType);
  assert.deepEqual(types, ["report", "lesson_plan", "blog", "quiz", "ppt", "flashcard", "mind_map", "game", "classroom"]);
  assert.equal(new Set(types).size, 9);
});

test("every generation resource has teacher-facing copy", () => {
  for (const item of generationRegistry) {
    assert.ok(item.label.trim());
    assert.ok(item.description.trim());
  }
});
