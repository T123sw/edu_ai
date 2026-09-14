import assert from "node:assert/strict";
import test from "node:test";

import { generationPromptDraftKey } from "./generationPromptDraft.ts";

test("draft keys isolate owner, course, scope, and resource type", () => {
  const base = {
    ownerUserId: "teacher-a",
    courseId: "course-a",
    scopeType: "knowledge_point" as const,
    scopeId: "kp-1",
    resourceType: "report" as const,
  };
  const keys = [
    generationPromptDraftKey(base),
    generationPromptDraftKey({ ...base, ownerUserId: "student-a" }),
    generationPromptDraftKey({ ...base, courseId: "course-b" }),
    generationPromptDraftKey({ ...base, scopeId: "kp-2" }),
    generationPromptDraftKey({ ...base, resourceType: "quiz" }),
  ];
  assert.equal(new Set(keys).size, keys.length);
});
