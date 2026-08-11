import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { formatAssessmentRatio, getAssessmentQueueLabel } from "./assessmentAnalyticsPresentation";


describe("teacher assessment analytics presentation", () => {
  it("always shows the numerator and denominator", () => {
    assert.equal(formatAssessmentRatio({ numerator: 1, denominator: 4, rate: 0.25 }), "25%（1/4）");
    assert.equal(formatAssessmentRatio({ numerator: 0, denominator: 0, rate: 0 }), "0%（0/0）");
  });

  it("uses actionable queue labels", () => {
    assert.equal(getAssessmentQueueLabel("pending_review"), "待教师复核");
    assert.equal(getAssessmentQueueLabel("attempts_exhausted"), "次数用尽未通过");
    assert.equal(getAssessmentQueueLabel("retry_available"), "可重做未通过");
  });

  it("wires analytics and review into the teacher task page", () => {
    const page = readFileSync(new URL("../pages/CourseLearning.tsx", import.meta.url), "utf8");
    const analytics = readFileSync(new URL("./AssessmentAnalytics.tsx", import.meta.url), "utf8");
    assert.match(page, /AssessmentAnalytics/);
    assert.match(analytics, /提交复核/);
    assert.match(analytics, /题目分析/);
    assert.match(analytics, /知识点分析/);
  });
});
