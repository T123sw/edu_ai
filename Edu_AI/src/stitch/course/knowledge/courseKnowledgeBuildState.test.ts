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
  assert.match(validateCourseKnowledgeConfig(invalid).join("；"), /网络资料下限/);
});
