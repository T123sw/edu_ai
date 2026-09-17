import assert from "node:assert/strict";
import { test } from "node:test";
import { allResources, seedState } from "./model";
import { addToLearning } from "./library";

test("adding a personal work preserves its source, creates one learning copy and keeps the current position", () => {
  const state = seedState(true);
  const room = state.rooms[0];
  const work = state.resources[0];
  const next = addToLearning(state, room.id, room.chapters[1].id, work);
  assert.equal(next.rooms[0].selectedId, room.selectedId);
  assert.equal(next.resources[0], work);
  const added = allResources(next.rooms[0]).find(r => r.sourceResourceId === work.id)!;
  assert.ok(added);
  assert.notEqual(added.id, work.id);
  assert.equal(addToLearning(next, room.id, room.chapters[1].id, work), next);
  assert.equal(allResources(state.rooms[0]).some(r => r.id === added.id), false);
});
