import assert from "node:assert/strict";
import test from "node:test";

import { courseKnowledgeActions, personalKnowledgeActions } from "./studentKnowledgeActions.ts";

test("student course knowledge exposes exploration but no course writes", () => {
  assert.deepEqual(courseKnowledgeActions, ["search", "select", "preview", "expand", "collapse", "pan", "zoom", "jump_to_ai"]);
  for (const forbidden of ["upload", "rename", "delete", "retry", "reindex", "attach_to_node", "save_graph", "textbook_import"]) {
    assert.equal(courseKnowledgeActions.includes(forbidden as never), false);
  }
});

test("personal knowledge exposes owner management but never course publication", () => {
  assert.deepEqual(personalKnowledgeActions, ["upload", "preview", "rename", "delete", "retry", "jump_to_ai"]);
  assert.equal(personalKnowledgeActions.includes("add_to_course" as never), false);
});
