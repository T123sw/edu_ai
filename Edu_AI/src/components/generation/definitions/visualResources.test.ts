import assert from "node:assert/strict";
import test from "node:test";

import { generationRegistry } from "../generationRegistry";
import { classroomDefinition } from "./classroom";
import { mindMapDefinition } from "./mindMap";
import { pptDefinition } from "./ppt";
import { classroomPageDefinition } from "../../../stitch/pages/classroomPageDefinition";

const source = { mode: "none" as const, selectedDocumentIds: [] };

test("mind-map description and depth are serialized", () => {
  const config = { ...mindMapDefinition.defaultConfig(), topic: "电磁学", description: "突出概念关系", depth: 4 };
  const payload = mindMapDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.description, "突出概念关系");
  assert.equal(payload.max_depth, 4);
});

test("PPT outline is structured and survives serialization", () => {
  const config = { ...pptDefinition.defaultConfig(), deckTitle: "电磁感应", outline: [{ id: "slide-1", title: "导入", keyPoints: ["生活现象"], speakerNotes: "提问", visualInstruction: "线圈示意图" }] };
  const payload = pptDefinition.serialize({ courseId: "course-1", source, config });
  assert.deepEqual(payload.outline, config.outline);
  assert.equal(JSON.stringify(payload).includes("outlineText"), false);
});

test("classroom voice and teaching settings reach the request", () => {
  const config = { ...classroomDefinition.defaultConfig(), topic: "波的干涉", objectives: ["解释相干条件"], voiceEnabled: true, voice: "nova", sceneCount: 8 };
  const payload = classroomDefinition.serialize({ courseId: "course-1", source, config });
  assert.equal(payload.voice, "nova");
  assert.equal(payload.enable_tts, true);
  assert.equal(payload.scene_count, 8);
  assert.deepEqual(payload.objectives, ["解释相干条件"]);
});

test("factory and classroom page use the same definition", () => {
  assert.equal(generationRegistry.find((item) => item.resourceType === "classroom")?.definition, classroomDefinition);
  assert.equal(classroomPageDefinition, classroomDefinition);
});
