import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("current course knowledge view owns course uploads and embeds the reusable build card", async () => {
  const source = await readFile(new URL("./KnowledgeDocumentsView.tsx", import.meta.url), "utf8");
  const buildCard = await readFile(new URL("./CourseKnowledgeBuildCard.tsx", import.meta.url), "utf8");
  const wizard = await readFile(new URL("./CourseKnowledgeBuildWizard.tsx", import.meta.url), "utf8");
  const textbookStep = await readFile(new URL("./CourseKnowledgeTextbookStep.tsx", import.meta.url), "utf8");
  const graphStep = await readFile(new URL("./CourseKnowledgeGraphReviewStep.tsx", import.meta.url), "utf8");

  assert.match(source, /libraryType: "course"/);
  assert.doesNotMatch(source, /libraryType: "personal"/);
  assert.match(source, /<CourseKnowledgeBuildCard/);
  assert.match(source, /edu-ai:knowledge-document-updated/);
  assert.match(source, /deleteKnowledgeBaseDocument/);
  assert.match(source, /删除当前节点下的文档/);
  assert.doesNotMatch(buildCard, /deleteCourseKnowledgeBase/);
  assert.doesNotMatch(buildCard, /删除课程知识库/);
  assert.match(buildCard, /createCourseKnowledgeBuildDraft/);
  assert.doesNotMatch(buildCard, /startCourseKnowledgeBuild/);
  assert.match(buildCard, /rollbackCourseKnowledgeVersion/);
  assert.doesNotMatch(buildCard, /buildKnowledgeBaseFromOpenTextbook/);
  assert.match(buildCard, /CourseKnowledgeBuildWizard/);
  assert.match(wizard, /updateCourseKnowledgeBuildDraft/);
  assert.match(wizard, /generateCourseKnowledgeGraphDraft/);
  assert.match(wizard, /saveCourseKnowledgeGraphDraft/);
  assert.match(wizard, /confirmCourseKnowledgeGraph/);
  assert.match(wizard, /startCourseKnowledgeBuild/);
  assert.match(graphStep, /重新生成此模块/);
  assert.match(graphStep, /确认图谱并开始构建/);
  assert.match(graphStep, /重新生成会丢弃尚未保存的图谱修改/);
  assert.match(textbookStep, /accept="\.pdf,\.docx,\.txt,\.md"/);
  assert.match(textbookStep, /可跳过/);
});

test("course knowledge build card keeps the primary experience simple", async () => {
  const buildCard = await readFile(new URL("./CourseKnowledgeBuildCard.tsx", import.meta.url), "utf8");

  assert.match(buildCard, /一键构建知识库/);
  assert.match(buildCard, /历史版本与更多信息/);
  assert.match(buildCard, /<details className="course-kb-builder__details">/);
  assert.match(buildCard, /createCourseKnowledgeBuildDraft\(courseId\)/);
  assert.doesNotMatch(buildCard, /previewCourseKnowledgeBuild\(courseId\)[\s\S]*startCourseKnowledgeBuild/);
  assert.doesNotMatch(buildCard, /质量门禁已通过/);
  assert.doesNotMatch(buildCard, /审核来源与许可/);
  assert.doesNotMatch(buildCard, /图谱结构：/);
});
