import assert from "node:assert/strict";
import test from "node:test";

import {
  buildQueuedAgentRequest,
  normalizeGenerationBrief,
} from "./generationAgentRequest.ts";

test("builds immutable Agent requests for every generation resource", () => {
  const cases = [
    ["report", "report"],
    ["lesson_plan", "lesson_plan"],
    ["blog", "blog"],
    ["quiz", "quiz"],
    ["flashcard", "flashcard"],
    ["mind_map", "graph"],
    ["game", "game"],
    ["classroom", "classroom"],
  ] as const;

  for (const [resourceType, canonicalType] of cases) {
    const request = buildQueuedAgentRequest({
      requestId: `request-${resourceType}`,
      text: "  我的真实要求  ",
      resourceType,
      ownerUserId: "teacher-a",
      courseId: "course-a",
      scopeType: "course",
      sourceMode: "none",
      selectedDocumentIds: [],
      allowWeb: false,
    });

    assert.equal(request.text, "我的真实要求");
    assert.equal(request.resourceType, canonicalType);
    assert.equal(request.actionHint, `generate.${canonicalType}`);
    assert.equal(request.entryMode, "generation_factory");
    assert.equal(request.allowRag, false);
    assert.ok(Object.isFrozen(request));
    assert.ok(Object.isFrozen(request.selectedDocumentIds));
  }
});

test("selected sources are normalized without changing the user text", () => {
  const request = buildQueuedAgentRequest({
    requestId: "request-selected",
    text: "生成 8 道题，不要加入示例占位文字",
    resourceType: "quiz",
    ownerUserId: "teacher-a",
    courseId: "course-a",
    scopeType: "knowledge_point",
    scopeId: "kp-1",
    sourceMode: "selected_documents",
    selectedDocumentIds: [" doc-1 ", "doc-1", "doc-2"],
    allowWeb: true,
  });

  assert.deepEqual(request.selectedDocumentIds, ["doc-1", "doc-2"]);
  assert.equal(request.allowRag, true);
  assert.equal(request.allowWeb, true);
  assert.equal(request.text, "生成 8 道题，不要加入示例占位文字");
});

test("rejects empty requirements and invalid workspace or source snapshots", () => {
  const base = {
    requestId: "request-invalid",
    text: "有效要求",
    resourceType: "report" as const,
    ownerUserId: "teacher-a",
    courseId: "course-a",
    scopeType: "course" as const,
    sourceMode: "none" as const,
    selectedDocumentIds: [] as string[],
    allowWeb: false,
  };

  assert.throws(() => buildQueuedAgentRequest({ ...base, text: "   " }), /请输入生成要求/);
  assert.throws(() => buildQueuedAgentRequest({ ...base, courseId: "" }), /课程/);
  assert.throws(() => buildQueuedAgentRequest({ ...base, scopeType: "knowledge_point", scopeId: "" }), /知识点/);
  assert.throws(() => buildQueuedAgentRequest({ ...base, sourceMode: "selected_documents" }), /至少选择一份资料/);
});

test("normalization only trims and never substitutes examples", () => {
  assert.equal(normalizeGenerationBrief("  请生成课堂  "), "请生成课堂");
  assert.equal(normalizeGenerationBrief("  "), "");
});
