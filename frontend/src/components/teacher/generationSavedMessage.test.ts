import assert from "node:assert/strict";
import test from "node:test";

import {
  buildGenerationSavedMessage,
  resolveGenerationReply,
} from "./generationSavedMessage.ts";

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

test("synchronous generation replaces legacy server copy with private visibility", () => {
  assert.equal(
    resolveGenerationReply({
      generatedResourceCount: 1,
      fallbackMessage: "生成完成，结果已保存到课程资源",
    }),
    "生成完成，已保存到“我的资源”，仅你可见。",
  );
});

test("polled generation keeps ordinary chat replies when no resource was created", () => {
  assert.equal(
    resolveGenerationReply({
      generatedResourceCount: 0,
      fallbackMessage: "这是普通问答回复。",
    }),
    "这是普通问答回复。",
  );
});
