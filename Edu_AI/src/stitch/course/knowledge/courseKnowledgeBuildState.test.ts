import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_COURSE_KNOWLEDGE_CONFIG,
  applyCourseKnowledgePreset,
  estimateCourseKnowledgeBuild,
  validateCourseKnowledgeConfig,
} from "./courseKnowledgeBuildState";

test("standard preset is the default and estimates sixteen leaves", () => {
  assert.equal(DEFAULT_COURSE_KNOWLEDGE_CONFIG.preset, "standard");
  assert.equal(DEFAULT_COURSE_KNOWLEDGE_CONFIG.prefer_complete_textbooks, true);
  assert.equal(DEFAULT_COURSE_KNOWLEDGE_CONFIG.max_online_textbooks, 2);
  assert.equal(DEFAULT_COURSE_KNOWLEDGE_CONFIG.max_search_rounds_per_leaf, 2);
  assert.deepEqual(estimateCourseKnowledgeBuild(DEFAULT_COURSE_KNOWLEDGE_CONFIG), {
    leafCount: 16,
    materialCount: 48,
  });
});

test("preset selection remains editable and manual limits are validated", () => {
  const large = applyCourseKnowledgePreset(DEFAULT_COURSE_KNOWLEDGE_CONFIG, "large");
  assert.equal(large.target_module_count, 6);
  assert.equal(large.target_points_per_module, 6);
  assert.equal(estimateCourseKnowledgeBuild(large).leafCount, 36);

  const invalid = {
    ...large,
    preset: "custom" as const,
    target_materials_per_leaf: 2,
    minimum_web_materials_per_leaf: 3,
  };
  assert.match(validateCourseKnowledgeConfig(invalid).join("；"), /外部非 AI 来源下限/);

  assert.match(validateCourseKnowledgeConfig({
    ...large,
    max_online_textbooks: 6,
    max_search_rounds_per_leaf: 4,
  }).join("；"), /在线教材上限.*搜索轮次/);
});
