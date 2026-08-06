import assert from "node:assert/strict";
import test from "node:test";

import { flashcardDefinition } from "./flashcard";
import { gameDefinition } from "./game";
import { quizDefinition } from "./quiz";

const source = { mode: "none" as const, selectedDocumentIds: [] };

test("quiz answer and explanation switches are independent", () => {
  const config = { ...quizDefinition.defaultConfig(), topic: "力学", audience: "大学一年级", count: 10, questionTypes: ["choice" as const, "short" as const], includeAnswers: true, includeExplanations: false };
  const payload = quizDefinition.serialize({ courseId: "course-1", source, config });
  const quiz = payload.quiz_config as Record<string, unknown>;
  assert.equal(quiz.include_answers, true);
  assert.equal(quiz.include_explanations, false);
  assert.deepEqual(quiz.question_types, ["choice", "short"]);
});

test("quiz requires at least one supported question type", () => {
  assert.equal(quizDefinition.validate({ ...quizDefinition.defaultConfig(), questionTypes: [] }).questionTypes, "至少选择一种题型");
});

test("flashcard title remains plain text and all settings serialize", () => {
  const config = { ...flashcardDefinition.defaultConfig(), title: "https://example.com/不是外链", count: 18, category: "核心概念", showSource: false };
  const payload = flashcardDefinition.serialize({ courseId: "course-1", source, config });
  const cards = payload.flashcard_config as Record<string, unknown>;
  assert.equal(cards.title, config.title);
  assert.equal(cards.count, 18);
  assert.equal(cards.show_sources, false);
});

test("game card count is required and bounded", () => {
  assert.equal(gameDefinition.validate({ ...gameDefinition.defaultConfig(), cardCount: 0 }).cardCount, "卡片数量需为 4–30");
  assert.equal(gameDefinition.validate({ ...gameDefinition.defaultConfig(), cardCount: 31 }).cardCount, "卡片数量需为 4–30");
});

test("game duration and difficulty reach the command", () => {
  const config = { ...gameDefinition.defaultConfig(), topic: "概念分类", gameType: "memory_flip" as const, cardCount: 12, difficulty: "hard" as const, durationMinutes: 8 };
  const payload = gameDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.game_type, "memory_flip");
  assert.equal(payload.card_count, 12);
  assert.equal(payload.difficulty, "hard");
  assert.equal(payload.duration_minutes, 8);
});
