import assert from "node:assert/strict";
import test from "node:test";

import { generationRegistry } from "../generationRegistry";
import { classroomDefinition } from "./classroom";
import { mindMapDefinition } from "./mindMap";
import { classroomPageDefinition } from "../../../stitch/pages/classroomPageDefinition";

const source = { mode: "none" as const, selectedDocumentIds: [] };

test("mind-map description and depth are serialized", () => {
  const config = { ...mindMapDefinition.defaultConfig(), topic: "电磁学", description: "突出概念关系", depth: 4 };
  const payload = mindMapDefinition.serialize({ courseId: "course-1", source, config });
  assert.ok(String(payload.description).startsWith("突出概念关系\n\n"));
  assert.match(String(payload.description), /summary.*短语或短句/);
  assert.match(String(payload.description), /不要截取原文首句/);
  assert.equal(payload.max_depth, 4);
});

test("mind-map preserves user requirements and reports an oversized prompt before submission", () => {
  const config = { ...mindMapDefinition.defaultConfig(), topic: "电磁学", description: "关系".repeat(1000) };
  assert.ok(mindMapDefinition.validate(config).description);
  assert.ok(String(mindMapDefinition.serialize({ courseId: "course-1", source, config }).description).startsWith(config.description));
});

test("classroom voice and teaching settings reach the request", () => {
  const config = { ...classroomDefinition.defaultConfig(), topic: "波的干涉", objectives: ["解释相干条件"], voiceEnabled: true, voice: "nova" };
  const payload = classroomDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.voice, "nova");
  assert.equal(payload.enable_tts, true);
  assert.equal(payload.scene_count, undefined);
  assert.equal(payload.duration_minutes, undefined);
  assert.equal(payload.teaching_style, undefined);
  assert.deepEqual(payload.objectives, ["解释相干条件"]);
});

test("factory and classroom page use the same definition", () => {
  assert.equal(generationRegistry.find((item) => item.resourceType === "classroom")?.definition, classroomDefinition);
  assert.equal(classroomPageDefinition, classroomDefinition);
});


test("classroom leaves media choices open and preserves explicit silence", () => {
  const config = { ...classroomDefinition.defaultConfig(), topic: "截距" };
  const defaults = classroomDefinition.serialize({ config } as any);
  assert.equal(defaults.enable_tts, undefined);
  assert.equal(defaults.include_visuals, undefined);
  const silent = classroomDefinition.serialize({ config: { ...config, voiceEnabled: false } } as any);
  assert.equal(silent.enable_tts, false);
});
