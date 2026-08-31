import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");

test("learning resource generation does not register a dedicated route", async () => {
  const [shared, teacherRoutes, navigation, app] = await Promise.all([
    source("../../shared.tsx"),
    source("../../teacherRoutes.ts"),
    source("../courseNavigation.ts"),
    source("../../App.tsx"),
  ]);

  assert.doesNotMatch(shared, /learningResourceGeneration:\s*["']learning-resource-generation["']/);
  assert.doesNotMatch(teacherRoutes, /["']learning-resource-generation["']/);
  assert.doesNotMatch(navigation, /routes:\s*\[[^\]]*["']learning-resource-generation["'][^\]]*\]/s);
  assert.doesNotMatch(app, /routes\.learningResourceGeneration/);
  assert.doesNotMatch(app, /LearningResourceGenerationPage/);
});

test("knowledge build card opens learning resource generation inline", async () => {
  const [card, panel] = await Promise.all([
    source("./CourseKnowledgeBuildCard.tsx"),
    source("./LearningResourceGenerationPanel.tsx"),
  ]);

  assert.doesNotMatch(card, /buildTeacherCourseHash\(["']learning-resource-generation["']/);
  assert.match(card, /const \[resourceConfigOpen, setResourceConfigOpen\] = useState\(false\)/);
  assert.match(card, /<button[\s\S]*onClick=\{[^}]*setResourceConfigOpen/s);
  assert.match(card, />\s*学习资源生成\s*</);
  assert.match(card, /resourceConfigOpen\s*\?\s*\(/);
  assert.match(card, /<LearningResourceGenerationPanel/);
  assert.match(panel, /role=["']dialog["']/);
  assert.match(panel, /aria-modal=["']false["']/);
  assert.match(panel, /<StandardLearningResources\s*\/>/);
  assert.match(panel, />\s*收起\s*</);
});

test("knowledge and resource configuration panels are mutually exclusive", async () => {
  const card = await source("./CourseKnowledgeBuildCard.tsx");

  assert.match(card, /setResourceConfigOpen\(false\);\s*setWizardOpen\(true\)/);
  assert.match(card, /setWizardOpen\(false\);\s*setResourceConfigOpen\(\(open\)\s*=>\s*!open\)/);
});

test("students keep read-only published resources", async () => {
  const knowledgePage = await source("../../pages/CourseKnowledge.tsx");
  assert.match(knowledgePage, /isStudent\s*\?\s*<StandardLearningResources\s+readOnly/);
});
