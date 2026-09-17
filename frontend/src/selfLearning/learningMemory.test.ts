import assert from "node:assert/strict";
import { test } from "node:test";
import { seedState, startShared } from "./model";
import { agentContext, chapterMessages, learningMemory } from "./learningMemory";
import { restoreState } from "./store";

test("knowledge point conversations restore legacy messages and bound context without mixing transcripts", () => {
  const state = seedState(true);
  const room = state.rooms[0];
  const [a, b] = room.chapters;
  room.messages = Array.from({ length: 20 }, (_, i) => ({ id: String(i), role: "user", text: `a-${i}`, resourceId: a.resources[i % a.resources.length].id, resourceTitle: a.title }));
  room.messages.push({ id: "b", role: "assistant", text: "private full transcript from B", chapterId: b.id, resourceId: b.resources[0].id, resourceTitle: b.title });
  room.understanding = { [b.id]: "review" };
  const restored = restoreState(JSON.stringify(state)).rooms[0];
  assert.equal(chapterMessages(restored, a.id).length, 20);
  assert.equal(chapterMessages(restored, b.id).length, 1);
  const context = agentContext(restored, a.id);
  assert.equal(context.recentMessages.length, 12);
  assert.equal(context.memory.find(m => m.chapterId === b.id)?.status, "待巩固");
  assert.equal(JSON.stringify(context).includes("private full transcript"), false);
});

test("global learning memory separates completion, quiz evidence and self assessment; shared learners start independently", () => {
  const state = seedState(true);
  const room = state.rooms[0];
  const chapter = room.chapters[0];
  room.progress = Object.fromEntries(chapter.resources.map(r => [r.id, { completed: true, position: 0, note: "" }]));
  assert.equal(learningMemory(room)[0].status, "学习中");
  room.progress[chapter.resources[0].id].answer = 0;
  assert.equal(learningMemory(room)[0].status, "建议回顾");
  room.understanding = { [chapter.id]: "understood" };
  assert.equal(learningMemory(room)[0].status, "自评已理解");
  assert.match(learningMemory(room)[0].facts, /0\/1 正确/);
  const [, joined] = startShared(state, room);
  assert.deepEqual(joined.understanding, {});
  assert.equal(learningMemory(joined)[0].status, "未开始");
});
