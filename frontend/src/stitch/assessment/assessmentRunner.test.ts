import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { deriveAssessmentRunnerState } from "./assessmentRunnerState";


describe("student assessment runner state", () => {
  it("covers initial, active, review, retry, completion, and reveal states", () => {
    assert.equal(deriveAssessmentRunnerState([], null), "ready");
    assert.equal(deriveAssessmentRunnerState([
      { status: "in_progress", result: null },
    ], null), "in_progress");
    assert.equal(deriveAssessmentRunnerState([
      { status: "pending_review", result: "pending_review" },
    ], { attempts_used: 1, max_attempts: 3, result: "pending_review", answers_revealed_at: null }), "pending_review");
    assert.equal(deriveAssessmentRunnerState([
      { status: "graded", result: "needs_retry" },
    ], { attempts_used: 1, max_attempts: 3, result: "needs_retry", answers_revealed_at: null }), "retry");
    assert.equal(deriveAssessmentRunnerState([
      { status: "graded", result: "passed" },
    ], { attempts_used: 2, max_attempts: 3, result: "passed", answers_revealed_at: null }), "passed");
    assert.equal(deriveAssessmentRunnerState([], {
      attempts_used: 3, max_attempts: 3, result: "needs_retry", answers_revealed_at: null,
    }), "exhausted");
    assert.equal(deriveAssessmentRunnerState([], {
      attempts_used: 2, max_attempts: 3, result: "passed", answers_revealed_at: "2026-08-12T00:00:00Z",
    }), "revealed");
  });

  it("is wired into the student learning task page", () => {
    const page = readFileSync(new URL("../pages/CourseLearning.tsx", import.meta.url), "utf8");
    const runner = readFileSync(new URL("./AssessmentRunner.tsx", import.meta.url), "utf8");
    assert.match(page, /AssessmentRunner/);
    assert.match(runner, /开始测评/);
    assert.match(runner, /提交测评/);
    assert.match(runner, /查看答案与解析/);
    assert.match(runner, /继续挑战/);
    assert.match(runner, /教师评语/);
    assert.match(runner, /student_comment/);
  });
});
