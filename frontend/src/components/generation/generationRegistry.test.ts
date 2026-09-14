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
    assert.ok(item.placeholder.trim());
    assert.equal(item.actionHint, `generate.${item.canonicalType}`);
  }
});

test("mind map is the only UI resource with a different canonical type", () => {
  assert.equal(generationRegistry.find((item) => item.resourceType === "mind_map")?.canonicalType, "graph");
  assert.equal(new Set(generationRegistry.map((item) => item.actionHint)).size, 8);
});

test("rendered generation resources require an explicit allowlist", () => {
  assert.deepEqual(selectGenerationResources([]), []);
  assert.deepEqual(
    selectGenerationResources(["report", "report", "flashcard"]).map((item) => item.resourceType),
    ["report", "flashcard"],
  );
});
