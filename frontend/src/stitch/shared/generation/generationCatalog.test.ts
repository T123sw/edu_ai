import assert from "node:assert/strict";
import test from "node:test";

import { sanitizeGenerationCatalog } from "./generationCatalog.ts";

test("generation catalog preserves authenticated server order and ignores duplicates", () => {
  assert.deepEqual(
    sanitizeGenerationCatalog([
      { tool_id: "report" },
      { tool_id: "mind_map" },
      { tool_id: "report" },
      { tool_id: "quiz" },
    ]),
    ["report", "mind_map", "quiz"],
  );
});

test("generation catalog rejects unknown tool ids instead of widening access", () => {
  assert.deepEqual(sanitizeGenerationCatalog([{ tool_id: "lesson_plan" }, { tool_id: "admin_tool" }, {}]), ["lesson_plan"]);
});

test("teacher and student catalogs match the exact product matrices", () => {
  const teacher = ["report", "mind_map", "quiz", "classroom", "lesson_plan", "blog"];
  const student = ["report", "mind_map", "quiz", "classroom", "flashcard", "game"];
  assert.deepEqual(sanitizeGenerationCatalog(teacher.map((tool_id) => ({ tool_id }))), teacher);
  assert.deepEqual(sanitizeGenerationCatalog(student.map((tool_id) => ({ tool_id }))), student);
});
