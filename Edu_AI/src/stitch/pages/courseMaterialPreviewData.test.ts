import assert from "node:assert/strict";
import test from "node:test";

import type { CourseMaterial } from "../api/types";
import { getQuizQuestions } from "./courseMaterialPreviewData";

test("quiz preview reads questions from generated material content", () => {
  const material = {
    material_id: "quiz-1",
    material_type: "quiz",
    content: { questions: [{ id: "q1", stem: "冒泡排序如何交换元素？", answer: "交换相邻逆序元素" }] },
  } satisfies CourseMaterial;
  assert.equal(getQuizQuestions(material).length, 1);
  assert.equal(getQuizQuestions(material)[0].stem, "冒泡排序如何交换元素？");
});

test("legacy top-level quiz questions remain supported", () => {
  const material = {
    material_id: "quiz-legacy",
    material_type: "quiz",
    questions: [{ id: "q1", stem: "题目" }],
  } satisfies CourseMaterial;
  assert.equal(getQuizQuestions(material).length, 1);
});
