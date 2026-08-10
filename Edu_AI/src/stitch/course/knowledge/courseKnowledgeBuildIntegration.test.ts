import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("current course knowledge view owns course uploads and embeds the reusable build card", async () => {
  const source = await readFile(new URL("./KnowledgeDocumentsView.tsx", import.meta.url), "utf8");
  const buildCard = await readFile(new URL("./CourseKnowledgeBuildCard.tsx", import.meta.url), "utf8");

  assert.match(source, /libraryType: "course"/);
  assert.doesNotMatch(source, /libraryType: "personal"/);
  assert.match(source, /<CourseKnowledgeBuildCard/);
  assert.match(source, /edu-ai:knowledge-document-updated/);
  assert.match(buildCard, /previewCourseKnowledgeBuild/);
  assert.match(buildCard, /startCourseKnowledgeBuild/);
  assert.match(buildCard, /rollbackCourseKnowledgeVersion/);
  assert.doesNotMatch(buildCard, /buildKnowledgeBaseFromOpenTextbook/);
});
