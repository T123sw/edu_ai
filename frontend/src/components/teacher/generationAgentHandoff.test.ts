import assert from "node:assert/strict";
import test from "node:test";

import {
  queuedAgentPromptDraftKey,
  validateQueuedAgentWorkspace,
} from "./generationAgentHandoff.ts";

const request = {
  requestId: "request-1",
  text: "生成报告",
  resourceType: "report" as const,
  actionHint: "generate.report" as const,
  ownerUserId: "teacher-a",
  courseId: "course-a",
  scopeType: "knowledge_point" as const,
  scopeId: "kp-1",
  sourceMode: "none" as const,
  selectedDocumentIds: [] as string[],
  allowRag: false,
  allowWeb: false,
};

test("accepts only the original owner, course, and workspace scope", () => {
  assert.equal(validateQueuedAgentWorkspace(request, {
    ownerUserId: "teacher-a",
    courseId: "course-a",
    scopeType: "knowledge_point",
    scopeId: "kp-1",
  }), null);

  assert.match(validateQueuedAgentWorkspace(request, {
    ownerUserId: "student-a",
    courseId: "course-a",
    scopeType: "knowledge_point",
    scopeId: "kp-1",
  }) || "", /账号/);
  assert.match(validateQueuedAgentWorkspace(request, {
    ownerUserId: "teacher-a",
    courseId: "course-b",
    scopeType: "knowledge_point",
    scopeId: "kp-1",
  }) || "", /课程/);
  assert.match(validateQueuedAgentWorkspace(request, {
    ownerUserId: "teacher-a",
    courseId: "course-a",
    scopeType: "course",
  }) || "", /知识点/);
});

test("recovery keeps the original account and maps graph back to its UI draft key", () => {
  assert.match(queuedAgentPromptDraftKey({
    ...request,
    resourceType: "graph",
    actionHint: "generate.graph",
  }), /teacher-a:course-a:knowledge_point:kp-1:mind_map$/);
});
