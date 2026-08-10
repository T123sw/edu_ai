import assert from "node:assert/strict";
import test from "node:test";

import { sourceSelectionId } from "./sourceSelectionIdentity";

test("managed course documents use their public id instead of a preview URL", () => {
  assert.equal(
    sourceSelectionId({
      key: "https://example.edu/course/document",
      documentId: "doc-v2-course-1",
    }),
    "doc-v2-course-1",
  );
});

test("legacy personal documents keep their storage key", () => {
  assert.equal(
    sourceSelectionId({ key: "user_student:D:/knowledge/notes.md" }),
    "user_student:D:/knowledge/notes.md",
  );
});
