import assert from "node:assert/strict";
import test from "node:test";

import {
  strongerCompletionBasis,
  taskNeedsAssessment,
  taskTypeLabel,
} from "./learningEvidencePresentation";

test("completion evidence strength is monotonic", () => {
  assert.equal(strongerCompletionBasis("self_reported", "activity_evidenced"), "activity_evidenced");
  assert.equal(strongerCompletionBasis("assessment_verified", "self_reported"), "assessment_verified");
  assert.equal(strongerCompletionBasis("none", "assessment_verified"), "assessment_verified");
});

test("only assessed tasks require assessment authoring", () => {
  assert.equal(taskNeedsAssessment({ task_type: "reading" }), false);
  assert.equal(taskNeedsAssessment({ task_type: "assessed" }), true);
  assert.equal(taskTypeLabel("reading"), "阅读学习");
  assert.equal(taskTypeLabel("assessed"), "考核任务");
});
