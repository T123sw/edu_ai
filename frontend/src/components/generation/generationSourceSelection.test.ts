import assert from "node:assert/strict";
import test from "node:test";

import {
  changeSourceMode,
  initialGenerationSource,
} from "./GenerationSourceSelector.tsx";

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

test("opening generation uses the documents selected in the left knowledge panel", () => {
  assert.deepEqual(initialGenerationSource(["doc-1", "doc-2"]), {
    mode: "selected_documents",
    selectedDocumentIds: ["doc-1", "doc-2"],
  });
});

test("opening generation without selected documents does not use knowledge by default", () => {
  assert.deepEqual(initialGenerationSource([]), {
    mode: "none",
    selectedDocumentIds: [],
  });
});
