import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  getLearningTaskPrimaryAction,
  getProgressLabel,
} from "./courseLearningPresentation";

describe("course learning presentation", () => {
  it("shows publish to teachers for a draft", () => {
    assert.equal(
      getLearningTaskPrimaryAction("teacher", {
        status: "draft",
        my_progress: null,
      }),
      "publish",
    );
  });

  it("shows continue to students for an in-progress task", () => {
    assert.equal(
      getLearningTaskPrimaryAction("student", {
        status: "published",
        my_progress: { status: "in_progress", progress_percent: 40 },
      }),
      "continue",
    );
    assert.equal(getProgressLabel(40), "已完成 40%");
  });

  it("clamps progress and distinguishes empty and complete states", () => {
    assert.equal(getProgressLabel(-5), "未开始");
    assert.equal(getProgressLabel(1000), "已完成");
    assert.equal(
      getLearningTaskPrimaryAction("student", {
        status: "published",
        my_progress: { status: "completed", progress_percent: 100 },
      }),
      "completed",
    );
  });
});
