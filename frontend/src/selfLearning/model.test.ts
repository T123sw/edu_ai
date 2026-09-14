import assert from "node:assert/strict";
import { test } from "node:test";
import {
  addClassroom,
  advanceJobs,
  allResources,
  createClassroom,
  createStudioJob,
  emptyEvidence,
  jobAction,
  seedState,
  sharedSeeds,
  startShared,
  updateEvidence,
} from "./model";
import { restoreState, storageKey } from "./store";

test("classroom prepares ordered resources monotonically, not workbench outputs", () => {
  const room = createClassroom("Agent 学习");
  let state = addClassroom(seedState(), room);
  for (let i = 1; i <= 16; i++) {
    state = advanceJobs(state, 1000);
    assert.equal(
      allResources(state.rooms[0]).filter((r) => r.ready).length,
      Math.floor((i / 16) * 9),
    );
    assert.equal(state.resources.length, 0);
  }
  assert.equal(state.jobs[0].status, "done");
});
test("cancel freezes generation; resume retains IDs; completion is idempotent", () => {
  const job = createStudioJob("MCP 对比报告", "report");
  let state = { ...seedState(), jobs: [job] };
  state = advanceJobs(state, 2000);
  state = jobAction(state, job.id, "cancel");
  state = advanceJobs(state, 10000);
  assert.equal(state.jobs[0].elapsed, 2000);
  assert.equal(state.resources.length, 0);
  state = jobAction(state, job.id, "retry");
  state = advanceJobs(state, 6000);
  state = advanceJobs(state, 6000);
  assert.equal(state.resources.length, 1);
  assert.equal(state.resources[0].id, job.resource!.id);
  assert.equal(state.jobs[0].status, "done");
});
test("shared classroom starts personal progress and resumes the same personal copy", () => {
  const shared = sharedSeeds()[0];
  const original = structuredClone(shared);
  const [state, room] = startShared(seedState(), shared);
  assert.notEqual(room.id, shared.id);
  assert.deepEqual(room.progress, {});
  const updated = updateEvidence(state, room.id, allResources(room)[0].id, {
    completed: true,
  });
  const [same, resumed] = startShared(updated, shared);
  assert.equal(resumed.id, room.id);
  assert.equal(same.rooms.length, updated.rooms.length);
  assert.deepEqual(shared, original);
});
test("progress, notes, current position and jobs survive storage restoration", () => {
  let state = seedState();
  const room = state.rooms[0];
  const resource = allResources(room)[0];
  state = updateEvidence(state, room.id, resource.id, {
    position: 23,
    note: "工具负责执行",
    completed: true,
  });
  const restored = restoreState(JSON.stringify(state));
  assert.deepEqual(restored.rooms[0].progress[resource.id], {
    ...emptyEvidence(),
    position: 23,
    note: "工具负责执行",
    completed: true,
  });
  assert.notEqual(storageKey("preview:探索者"), storageKey("preview:预览教师"));
  assert.notEqual(storageKey("preview:test"), storageKey("user:test"));
});
test("corrupt and incompatible cache safely falls back to sample data", () => {
  for (const raw of [
    "{bad",
    '{"version":2}',
    '{"version":1,"rooms":[{}],"jobs":[],"resources":[]}',
  ])
    assert.equal(restoreState(raw).rooms[0].id, "sample-agent");
});
