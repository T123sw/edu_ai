import test from 'node:test';
import assert from 'node:assert/strict';
import { applyProjection, newerProjection, type Projection } from './learningState';
import type { Classroom } from '../selfLearning/model';
const ref = { course_id: 'course', material_type: 'report', material_id: 'doc', version: 1 };
const room: Classroom = { id: 'course', title: 'course', goal: '', tone: '', selectedId: 'doc', messages: [], updatedAt: 0,
  chapters: [{ id: 'a', title: 'A', resources: [{ id: 'doc', title: '', topic: '', kind: 'report', ready: true, minutes: 1, createdAt: 0,
    remote: { courseId: 'course', materialId: 'doc', materialType: 'report', version: 1, visibility: 'course' } }] }], progress: {} };
const projection: Projection = { facts_revision: 1, resources: [{ resource_ref: ref, opened: true, reached_end: true, completed: false, locator: { kind: 'document', scroll_top: 500 } }], resource_revisions: [], self_assessments: { a: 'understood' }, self_assessment_revisions: {}, topics: [], next_actions: {} };
test('reading and self assessment do not imply completion; old versions never carry over', () => {
  assert.equal(applyProjection(room, projection).progress.doc.completed, false);
  const completed = { ...projection, resources: [{ ...projection.resources[0], completed: true }] };
  assert.equal(applyProjection(room, completed).progress.doc.completed, true);
  const newVersion = structuredClone(room); newVersion.chapters[0].resources[0].remote!.version = 2;
  assert.equal(applyProjection(newVersion, completed).progress.doc.completed, false);
});
test('late receipt cannot roll back a newer server projection', () => {
  const latest = { ...projection, facts_revision: 4 };
  assert.equal(newerProjection(latest, projection), latest);
});
test('persisted events are separated by owner and retain identities when reopening', async () => {
  const { readPending } = await import('./learningState');
  const entries = new Map([
    ['alice:course:e1', JSON.stringify({ topic: 'a', event: { event_id: 'e1', occurred_at: '2026-09-17T00:00:00Z' } })],
    ['bob:course:e2', JSON.stringify({ topic: 'b', event: { event_id: 'e2', occurred_at: '2026-09-17T00:00:00Z' } })],
  ]);
  const storage = { length: entries.size, key: (index: number) => [...entries.keys()][index], getItem: (key: string) => entries.get(key) || null };
  assert.deepEqual(readPending(storage, 'alice:course').map(p => p.event.event_id), ['e1']);
  assert.deepEqual(readPending(storage, 'bob:course').map(p => p.event.event_id), ['e2']);
});
test('reading queue coalesces only unsent positions in the same stream; explicit actions survive', async () => {
  const { coalesceReading } = await import('./learningState');
  const pending = (id: string, type = 'reading_position_set', stream = 'stream') => ({ topic: 'a', event: {
    schema_version: 1 as const, event_id: id, type, resource_ref: ref, manifest_ref: null, expected_revision: null,
    occurred_at: '2026-09-17T00:00:00Z', payload: { stream_id: stream },
  } });
  const queue = [pending('in-flight'), pending('old'), pending('completion', 'resource_completion_set'), pending('other', 'reading_position_set', 'other-stream')];
  assert.deepEqual(coalesceReading(queue, pending('latest'), 'in-flight').map(p => p.event.event_id), ['in-flight', 'completion', 'other', 'latest']);
});
