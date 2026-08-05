import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const source = readFileSync(
  fileURLToPath(new URL("./ChatPanel.tsx", import.meta.url)),
  "utf8",
);

describe("ChatPanel empty state", () => {
  it("replaces the component-library default with course-specific guidance", () => {
    assert.match(source, /locale=\{\{/);
    assert.match(source, /开始一段课程对话/);
    assert.match(source, /从下方输入问题/);
  });
});
