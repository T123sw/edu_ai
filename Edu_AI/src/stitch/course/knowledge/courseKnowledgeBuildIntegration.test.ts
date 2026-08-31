import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("current course knowledge view owns course uploads and embeds the reusable build card", async () => {
  const source = await readFile(new URL("./KnowledgeDocumentsView.tsx", import.meta.url), "utf8");
  const buildCard = await readFile(new URL("./CourseKnowledgeBuildCard.tsx", import.meta.url), "utf8");
  const wizard = await readFile(new URL("./CourseKnowledgeBuildWizard.tsx", import.meta.url), "utf8");
  const textbookStep = await readFile(new URL("./CourseKnowledgeTextbookStep.tsx", import.meta.url), "utf8");
  const graphStep = await readFile(new URL("./CourseKnowledgeGraphReviewStep.tsx", import.meta.url), "utf8");
  const graphSummary = await readFile(new URL("./KnowledgeGraphReviewSummary.tsx", import.meta.url), "utf8");
  const graphTree = await readFile(new URL("./KnowledgeGraphTree.tsx", import.meta.url), "utf8");
  const nodeEditor = await readFile(new URL("./KnowledgeGraphNodeEditor.tsx", import.meta.url), "utf8");
  const reviewActions = await readFile(new URL("./KnowledgeGraphReviewActions.tsx", import.meta.url), "utf8");
  const configStep = await readFile(new URL("./CourseKnowledgeBuildConfigStep.tsx", import.meta.url), "utf8");

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
  assert.match(nodeEditor, /重新生成此模块/);
  assert.match(reviewActions, /确认图谱并开始构建/);
  assert.match(graphStep, /重新生成会丢弃尚未保存的图谱修改/);
  assert.match(buildCard, /增量更新知识库/);
  assert.match(configStep, /增量追加/);
  assert.match(configStep, /高级设置/);
  assert.match(configStep, /完全重建/);
  assert.match(configStep, /window\.confirm/);
  assert.match(graphStep, /selectedNodeId/);
  assert.match(graphStep, /expandedNodeIds/);
  assert.match(graphStep, /mobilePane/);
  assert.match(graphStep, /KnowledgeGraphReviewSummary/);
  assert.match(graphStep, /KnowledgeGraphTree/);
  assert.match(graphStep, /KnowledgeGraphNodeEditor/);
  assert.match(graphStep, /KnowledgeGraphReviewActions/);
  assert.doesNotMatch(graphStep, /function NodeEditor/);
  assert.match(graphSummary, /本次新增/);
  assert.match(graphSummary, /待完善/);
  assert.match(graphTree, /role="tree"/);
  assert.match(graphTree, /aria-expanded/);
  assert.match(nodeEditor, /当前节点/);
  assert.match(nodeEditor, /现有节点的名称、类型和位置受保护/);
  assert.match(reviewActions, /保存草案/);
  assert.match(textbookStep, /accept="\.pdf,\.docx,\.txt,\.md"/);
  assert.match(textbookStep, /可跳过/);
});

test("first and update build wizards keep the continue action reachable", async () => {
  const shellStyles = await readFile(new URL("../../styles.css", import.meta.url), "utf8");
  const wizardStyles = await readFile(new URL("./CourseKnowledgeBuildCard.css", import.meta.url), "utf8");

  assert.match(
    shellStyles,
    /\.knowledge-library__content\s*\{[^}]*overflow-y:\s*auto;/s,
  );
  assert.match(
    wizardStyles,
    /\.course-kb-wizard__footer\s*\{[^}]*position:\s*sticky;[^}]*bottom:\s*0;/s,
  );
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
