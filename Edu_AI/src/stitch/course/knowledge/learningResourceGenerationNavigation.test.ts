import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");

test("course knowledge exposes learning resource generation as a dedicated route", async () => {
  const [shared, teacherRoutes, navigation, app] = await Promise.all([
    source("../../shared.tsx"),
    source("../../teacherRoutes.ts"),
    source("../courseNavigation.ts"),
    source("../../App.tsx"),
  ]);

  assert.match(shared, /learningResourceGeneration:\s*["']learning-resource-generation["']/);
  assert.match(teacherRoutes, /["']learning-resource-generation["']/);
  assert.match(navigation, /routes:\s*\[[^\]]*["']learning-resource-generation["'][^\]]*\]/s);
  assert.match(app, /routes\.learningResourceGeneration/);
  assert.match(app, /LearningResourceGenerationPage/);
});

test("knowledge build card links editors to learning resource generation", async () => {
  const card = await source("./CourseKnowledgeBuildCard.tsx");
  assert.match(card, /buildTeacherCourseHash\(["']learning-resource-generation["'],\s*courseId\)/);
  assert.match(card, />\s*学习资源生成\s*</);
});

test("teachers configure resources on the dedicated page while students keep read-only resources", async () => {
  const [knowledgePage, generationPage] = await Promise.all([
    source("../../pages/CourseKnowledge.tsx"),
    source("../../pages/LearningResourceGeneration.tsx"),
  ]);

  assert.match(knowledgePage, /isStudent\s*\?\s*<StandardLearningResources\s+readOnly/);
  assert.match(generationPage, /<StandardLearningResources\s*\/>/);
  assert.match(generationPage, /学习资源生成/);
  assert.match(generationPage, /返回课程知识/);
});
