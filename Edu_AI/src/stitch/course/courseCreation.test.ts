import assert from "node:assert/strict";
import test from "node:test";

import { buildCourseCreatePayload, EMPTY_COURSE_CREATION_DRAFT } from "./courseCreation.ts";

test("course creation requires semantic fields used by knowledge planning", () => {
  const result = buildCourseCreatePayload(EMPTY_COURSE_CREATION_DRAFT);

  assert.equal(result.payload, null);
  assert.deepEqual(Object.keys(result.errors).sort(), ["audience", "description", "objectivesText", "title"]);
});

test("course creation normalizes objectives and leaves id generation to the server", () => {
  const result = buildCourseCreatePayload({
    title: "  线性代数  ",
    description: " 面向工程问题的线性代数课程 ",
    audience: " 大一学生 ",
    objectivesText: "理解向量空间\n\n 掌握矩阵分解 ",
    language: "zh-CN",
    difficulty: "intermediate",
  });

  assert.deepEqual(result.errors, {});
  assert.equal(result.payload?.id, undefined);
  assert.deepEqual(result.payload?.objectives, ["理解向量空间", "掌握矩阵分解"]);
  assert.equal(result.payload?.title, "线性代数");
  assert.equal(result.payload?.audience, "大一学生");
});
