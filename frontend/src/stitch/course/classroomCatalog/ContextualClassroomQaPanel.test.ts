import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (relativePath: string) => readFile(new URL(relativePath, import.meta.url), "utf8");

test("contextual QA names the active resource and full context scope", async () => {
  const [contextPanel, panel] = await Promise.all([
    source("./ContextualClassroomQaPanel.tsx"),
    source("../../classroomQa/ClassroomQaPanel.tsx"),
  ]);
  assert.match(contextPanel, /正在围绕/);
  assert.match(contextPanel, /已读取完整文档/);
  assert.match(contextPanel, /已读取完整习题/);
  assert.match(contextPanel, /已读取完整课堂/);
  assert.match(panel, /supportsPlaybackInterruption/);
  assert.doesNotMatch(panel, /ClassroomInterruptionController/);
  assert.match(panel, /停止回答并继续授课/);
  assert.match(panel, /停止回答/);
});

test("empty loading and error states do not render a question composer", async () => {
  const contextPanel = await source("./ContextualClassroomQaPanel.tsx");
  assert.match(contextPanel, /status === "empty"/);
  assert.match(contextPanel, /status === "loading"/);
  assert.match(contextPanel, /status === "error"/);
  assert.match(contextPanel, /onRetry/);
  assert.match(contextPanel, /<ClassroomQaPanel/);
});
