import assert from "node:assert/strict";
import test from "node:test";

import { buildGenerationSavedMessage } from "./generationSavedMessage.ts";

test("generation completion explains that the new resource is private", () => {
  assert.equal(
    buildGenerationSavedMessage({ visibility: "private" }),
    "生成完成，已保存到“我的资源”，仅你可见。",
  );
});

test("shared generation completion names the course space", () => {
  assert.equal(
    buildGenerationSavedMessage({ visibility: "course" }),
    "生成完成，已保存到“课程共享”，课程成员可见。",
  );
});
