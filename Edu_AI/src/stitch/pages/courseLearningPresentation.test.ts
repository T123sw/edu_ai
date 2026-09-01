import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  getCompletionBasisLabel,
  getLearningTaskPrimaryAction,
  getProgressLabel,
  getTaskResourceEvidenceLabel,
  buildLearningResourceHref,
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
    assert.equal(getProgressLabel(40, "in_progress"), "进行中 · 40%");
  });

  it("clamps progress and distinguishes empty and complete states", () => {
    assert.equal(getProgressLabel(-5, "not_started"), "未开始");
    assert.equal(getProgressLabel(1000, "completed"), "已完成");
    assert.equal(
      getLearningTaskPrimaryAction("student", {
        status: "published",
        my_progress: { status: "completed", progress_percent: 100 },
      }),
      "completed",
    );
  });

  it("keeps in-progress learning distinct from completion evidence", () => {
    assert.equal(getProgressLabel(1, "in_progress"), "进行中 · 1%");
    assert.equal(getProgressLabel(100, "completed"), "已完成");
    assert.equal(getCompletionBasisLabel("self_reported"), "学生自报完成");
    assert.equal(getCompletionBasisLabel("activity_evidenced"), "已有活动证据");
    assert.equal(getCompletionBasisLabel("assessment_verified"), "测评已验证");
  });

  it("falls back legacy completed progress to self-reported without upgrading active work", () => {
    assert.equal(getCompletionBasisLabel(undefined, "completed"), "学生自报完成");
    assert.equal(getCompletionBasisLabel(null, "completed"), "学生自报完成");
    assert.equal(getCompletionBasisLabel(undefined, "in_progress"), "暂无完成证据");
  });

  it("shows resource evidence without changing task completion", () => {
    assert.equal(
      getTaskResourceEvidenceLabel({ condition_status: "satisfied", resource_version: 3 }),
      "资源条件已满足 · 证据版本 3",
    );
    assert.equal(
      getTaskResourceEvidenceLabel({ condition_status: "pending", resource_version: 4 }),
      "资源条件待完成 · 证据版本 4",
    );
  });
});

describe("learning resource destinations", () => {
  it("routes standard resources to the curriculum classroom", () => {
    assert.equal(buildLearningResourceHref("student", "course-1", {
      origin_type: "standard", scope_id: "leaf-1", material_id: "guide-1", material_type: "report",
    }), "#student-classroom?course_id=course-1&node_id=leaf-1&resource_id=guide-1");
  });

  it("keeps non-standard resources in resource management", () => {
    assert.equal(buildLearningResourceHref("teacher", "course-1", {
      origin_type: "personal", scope_id: null, material_id: "report-1", material_type: "report",
    }), "#resources?course_id=course-1&space=course&material_type=report&material_id=report-1");
  });
});
