import assert from "node:assert/strict";
import test from "node:test";

import { getStudentSourceActions } from "./studentSourceActions.ts";

test("student course sources are strictly select and preview only", () => {
  assert.deepEqual(getStudentSourceActions("course", "ready"), ["select", "preview"]);
});

test("student personal sources allow owner management and retry only on failure", () => {
  assert.deepEqual(getStudentSourceActions("personal", "ready"), ["select", "preview", "rename", "delete"]);
  assert.deepEqual(getStudentSourceActions("personal", "failed"), ["select", "preview", "rename", "delete", "retry"]);
});

test("student source actions never contain course mutations", () => {
  const actions = [...getStudentSourceActions("course", "failed"), ...getStudentSourceActions("personal", "failed")];
  for (const forbidden of ["add_to_course", "upload_course", "delete_course", "reindex", "associate_graph"]) {
    assert.equal(actions.includes(forbidden as never), false);
  }
});
