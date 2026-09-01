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

test("knowledge build card opens learning resource generation in a compact modal", async () => {
  const [card, panel] = await Promise.all([
    source("./CourseKnowledgeBuildCard.tsx"),
    source("./LearningResourceGenerationPanel.tsx"),
  ]);

  assert.doesNotMatch(card, /buildTeacherCourseHash\(["']learning-resource-generation["']/);
  assert.match(card, /const \[resourceConfigOpen, setResourceConfigOpen\] = useState\(false\)/);
  assert.match(card, /aria-expanded=\{resourceConfigOpen\}/);
  assert.match(panel, /import \{ Modal \} from ["']antd["']/);
  assert.match(panel, /<Modal[\s\S]*open[\s\S]*width=\{1080\}/);
  assert.match(panel, /destroyOnHidden/);
  assert.match(panel, /<StandardLearningResources\s+compact\s+onCancel=\{onClose\}/);
  assert.doesNotMatch(panel, /aria-modal=["']false["']/);
});

test("knowledge and resource configuration panels are mutually exclusive", async () => {
  const card = await source("./CourseKnowledgeBuildCard.tsx");

  assert.match(card, /setResourceConfigOpen\(false\);\s*setWizardOpen\(true\)/);
  assert.match(card, /setWizardOpen\(false\);\s*setResourceConfigOpen\(\(open\)\s*=>\s*!open\)/);
});

test("compact resources use progressive disclosure and a fixed action bar", async () => {
  const resources = await source("./StandardLearningResources.tsx");

  assert.match(resources, /compact\s*=\s*false/);
  assert.match(resources, /expandedLeafId/);
  assert.match(resources, /openChapterIds/);
  assert.match(resources, /standard-resource-leaf__compact-row/);
  assert.match(resources, /standard-resources__compact-footer/);
  assert.match(resources, /查看详情/);
  assert.match(resources, /toggleStandardResourceLeafScope/);
});

test("students keep read-only published resources", async () => {
  const knowledgePage = await source("../../pages/CourseKnowledge.tsx");
  assert.doesNotMatch(knowledgePage, /<StandardLearningResources\s+readOnly/);
  assert.match(knowledgePage, /<KnowledgeDocumentsView\s+readOnly=\{isStudent\}/);
});
