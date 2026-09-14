import assert from "node:assert/strict";
import test from "node:test";

import { materialExportFile } from "./materialExport.ts";

test("text resources export readable markdown", () => {
  const file = materialExportFile(
    { material_id: "r1", material_type: "report", title: "链表报告" },
    "# 链表报告\n\n正文",
  );
  assert.equal(file.filename, "链表报告.md");
  assert.equal(file.mimeType, "text/markdown;charset=utf-8");
});

test("structured resources export JSON", () => {
  const file = materialExportFile(
    { material_id: "q1", material_type: "quiz", title: "链表习题", questions: [] },
    "",
  );
  assert.equal(file.filename, "链表习题.json");
  assert.deepEqual(JSON.parse(file.content), { questions: [] });
});


test("native quiz and flashcard exports preserve generated content", () => {
  const questions = [{ id: "q1", type: "single_choice", stem: "2+3?", options: ["5", "6"], answer: "A", explanation: "相加为五" }];
  const cards = [{ id: "c1", front: "2+3?", back: "5" }];
  for (const [kind, content] of [["quiz", { title: "加法", questions }], ["flashcard", { title: "加法", cards }]] as const) {
    const file = materialExportFile({ material_id: "native", material_type: kind, content }, "");
    assert.deepEqual(JSON.parse(file.content), content);
  }
});
