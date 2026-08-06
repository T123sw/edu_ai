import assert from "node:assert/strict";
import test from "node:test";

import { changeSourceMode } from "./GenerationSourceSelector.tsx";

test("switching away from selected documents clears stale IDs", () => {
  assert.deepEqual(
    changeSourceMode({ mode: "selected_documents", selectedDocumentIds: ["doc-1"] }, "none"),
    { mode: "none", selectedDocumentIds: [] },
  );
});

test("selected-document mode preserves only explicit ready selections", () => {
  assert.deepEqual(
    changeSourceMode({ mode: "course_auto", selectedDocumentIds: [] }, "selected_documents"),
    { mode: "selected_documents", selectedDocumentIds: [] },
  );
});
