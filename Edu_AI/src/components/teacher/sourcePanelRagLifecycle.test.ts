import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("knowledge uploads register one global job and do not start a private poller", async () => {
  const source = await readFile(new URL("./SourcePanel.tsx", import.meta.url), "utf8");
  assert.match(source, /registerCreatedJob\(uploadResult\.job\)/);
  assert.match(source, /edu-ai:knowledge-document-updated/);
  assert.doesNotMatch(
    source,
    /pollKnowledge(?:Base)?(?:Document|Job)|setInterval[\s\S]{0,500}knowledge/i,
  );
});

test("knowledge documents expose lifecycle recovery and retrieval validation", async () => {
  const source = await readFile(new URL("./SourcePanel.tsx", import.meta.url), "utf8");
  assert.match(source, /KNOWLEDGE_STATUS_META/);
  assert.match(source, /retryKnowledgeBaseDocument/);
  assert.match(source, /reindexKnowledgeBaseDocument/);
  assert.match(source, /testKnowledgeBaseDocumentRetrieval/);
  assert.match(source, /只在当前文档的活动索引版本中检索/);
});
