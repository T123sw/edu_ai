import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GenerationPromptDialog } from "./GenerationPromptDialog.tsx";
import { generationSourceSummary } from "./GenerationSourceSelector.tsx";
import { getGenerationResource } from "./generationRegistry.ts";

test("renders one empty natural-language field with a non-submitted placeholder", () => {
  const resource = getGenerationResource("report");
  const html = renderToStaticMarkup(React.createElement(GenerationPromptDialog, {
    resource,
    value: "",
    source: { mode: "none", selectedDocumentIds: [] },
    documents: [],
    onValueChange: () => undefined,
    onSourceChange: () => undefined,
    onClose: () => undefined,
    onSubmit: () => undefined,
  }));

  assert.equal((html.match(/<textarea/g) || []).length, 1);
  assert.match(html, new RegExp(resource.placeholder.slice(0, 12)));
  assert.doesNotMatch(html, /<textarea[^>]*>[^<]+<\/textarea>/);
  assert.match(html, /交给 AI/);
  assert.doesNotMatch(html, /教学对象|报告风格|字数/);
});

test("source summaries remain concise", () => {
  assert.equal(generationSourceSummary({ mode: "none", selectedDocumentIds: [] }), "不使用知识库");
  assert.equal(generationSourceSummary({ mode: "course_auto", selectedDocumentIds: [] }), "自动检索课程资料");
  assert.equal(generationSourceSummary({ mode: "selected_documents", selectedDocumentIds: ["a", "b"] }), "已选择 2 份文档");
});
