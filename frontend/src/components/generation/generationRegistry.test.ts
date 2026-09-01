import assert from "node:assert/strict";
import test from "node:test";

import { generationRegistry, selectGenerationResources } from "./generationRegistry.ts";

test("registry contains exactly eight distinct resources", () => {
  const types = generationRegistry.map((item) => item.resourceType);
  assert.deepEqual(types, ["report", "lesson_plan", "blog", "quiz", "flashcard", "mind_map", "game", "classroom"]);
  assert.equal(new Set(types).size, 8);
});

test("every generation resource has teacher-facing copy", () => {
  for (const item of generationRegistry) {
    assert.ok(item.label.trim());
    assert.ok(item.description.trim());
  }
});

test("rendered generation resources require an explicit allowlist", () => {
  assert.deepEqual(selectGenerationResources([]), []);
  assert.deepEqual(
    selectGenerationResources(["report", "report", "flashcard"]).map((item) => item.resourceType),
    ["report", "flashcard"],
  );
});
