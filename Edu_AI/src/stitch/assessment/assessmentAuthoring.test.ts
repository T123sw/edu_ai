import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { getAssessmentPublishBlockers } from "./assessmentAuthoring";


describe("assessment authoring publication gate", () => {
  it("blocks publication when no assessment draft exists", () => {
    assert.deepEqual(getAssessmentPublishBlockers(null), ["请先配置正式测评"]);
  });

  it("surfaces concrete quality failures", () => {
    assert.deepEqual(
      getAssessmentPublishBlockers({
        status: "draft",
        items: [{ assessment_item_id: "asi-1" }],
        quality: {
          publishable: false,
          issues: [
            { code: "MISSING_SCORING_KEY", message: "客观题缺少答案" },
            { code: "KNOWLEDGE_POINT_UNCOVERED", message: "知识点 recursion 未覆盖" },
          ],
        },
      }),
      ["客观题缺少答案", "知识点 recursion 未覆盖"],
    );
  });

  it("allows a valid non-empty draft to publish", () => {
    assert.deepEqual(
      getAssessmentPublishBlockers({
        status: "draft",
        items: [{ assessment_item_id: "asi-1" }],
        quality: { publishable: true, issues: [] },
      }),
      [],
    );
  });

  it("wires the four-step teacher flow without a legacy publish fallback", () => {
    const editor = readFileSync(
      new URL("./AssessmentEditor.tsx", import.meta.url),
      "utf8",
    );
    const page = readFileSync(
      new URL("../pages/CourseLearning.tsx", import.meta.url),
      "utf8",
    );
    for (const label of ["任务目标", "学习材料", "正式测评", "发布设置"]) {
      assert.match(editor, new RegExp(label));
    }
    assert.match(page, /AssessmentEditor/);
    assert.match(page, /getAssessmentPublishBlockers/);
    assert.doesNotMatch(page, /legacyPublish|fallbackPublish/);
  });
});
