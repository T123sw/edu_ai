import assert from 'node:assert/strict';
import test from 'node:test';
import type { Classroom, LearningResource } from '../selfLearning/model';
import { mergeProgressiveCourse, withResourcePlaceholders } from './progressiveCourse';

const video = (id: string, ready = true): LearningResource => ({ id, title: id, topic: id,
  kind: 'video', ready, minutes: 1, createdAt: 0,
  ...(ready ? { remote: { courseId: 'c', materialId: id, materialType: 'classroom', version: 1, visibility: 'private' } } : {}) });
const room = (): Classroom => ({ id: 'c', title: 'course', goal: '', tone: '', updatedAt: 0,
  manifestRef: { manifest_id: 'm', version: 1 }, routeVersion: 1,
  preparationDelivery: { state: 'partial', preparationId: 'p', availableResources: 1, pending: [] },
  chapters: [{ id: 'a', title: 'a', resources: [video('one')] },
    { id: 'b', title: 'b', resources: [video('pending:b', false)] }],
  selectedId: 'one', messages: [], progress: { one: { position: 14, note: 'keep', completed: false } },
  understanding: { one: 'understood' } });
function delivered(before: Classroom): Classroom {
  const next = structuredClone(before);
  next.manifestRef!.version++;
  next.chapters[1].resources = [video('two')];
  next.preparationDelivery!.availableResources = 2;
  next.selectedId = 'two';
  next.progress = {};
  next.understanding = {};
  return next;
}

test('adds finished resources without replacing the playing resource or local progress', () => {
  const before = room(), merged = mergeProgressiveCourse(before, delivered(before));
  assert.equal(merged.manifestRef!.version, 2);
  assert.equal(merged.chapters[1].resources[0].id, 'two');
  assert.strictEqual(merged.chapters[0].resources[0], before.chapters[0].resources[0]);
  assert.equal(merged.selectedId, 'one');
  assert.deepEqual(merged.progress, before.progress);
  assert.deepEqual(merged.understanding, before.understanding);
});
test('a selected placeholder opens its own completed knowledge point', () => {
  const before = room(); before.selectedId = 'pending:b';
  assert.equal(mergeProgressiveCourse(before, delivered(before)).selectedId, 'two');
});
test('final publication keeps the current lesson mounted', () => {
  const before = room(), next = delivered(before); next.preparationDelivery!.state = 'complete';
  assert.equal(mergeProgressiveCourse(before, next).preparationDelivery!.state, 'complete');
  assert.strictEqual(mergeProgressiveCourse(before, next).chapters[0].resources[0], before.chapters[0].resources[0]);
});
test('revision, rollback, missing or replaced resources cannot silently change a live course', () => {
  for (const mutate of [
    (n: Classroom) => { n.routeVersion = 2; },
    (n: Classroom) => { n.manifestRef!.version = 0; },
    (n: Classroom) => { n.manifestRef!.manifest_id = 'another'; },
    (n: Classroom) => { n.preparationDelivery!.preparationId = 'another'; },
    (n: Classroom) => { n.chapters[0].resources = []; },
    (n: Classroom) => { n.chapters[0].resources[0].remote!.version = 2; },
  ]) {
    const before = room(), next = delivered(before); mutate(next);
    assert.strictEqual(mergeProgressiveCourse(before, next), before);
  }
});


test('every planned resource has a typed slot even when a sibling is ready', () => {
  const before = room();
  before.chapters[0].pendingResourceTypes = ['report', 'quiz'];
  before.chapters[1].pendingResourceTypes = ['classroom', 'report', 'quiz'];
  const normalized = withResourcePlaceholders(before);
  for (const chapter of normalized.chapters) assert.deepEqual(chapter.resources.map(r => r.kind), ['video', 'report', 'quiz']);
  assert.strictEqual(normalized.chapters[0].resources[0], before.chapters[0].resources[0]);
  assert.equal(normalized.chapters[0].resources.filter(r => !r.ready).length, 2);
  assert.strictEqual(withResourcePlaceholders(normalized), normalized);
});

test('selected quiz placeholder opens the delivered quiz instead of the video', () => {
  const before = room(); before.chapters[0].pendingResourceTypes = ['quiz'];
  const normalized = withResourcePlaceholders(before);
  normalized.selectedId = 'pending:a:quiz';
  const next = structuredClone(normalized); next.manifestRef!.version++;
  next.chapters[0].pendingResourceTypes = [];
  next.chapters[0].resources[1] = { ...video('quiz-done'), kind: 'quiz' };
  const merged = mergeProgressiveCourse(normalized, next);
  assert.equal(merged.selectedId, 'quiz-done');
  assert.strictEqual(merged.chapters[0].resources[0], normalized.chapters[0].resources[0]);
});

test('disabled video is not invented as a planned resource', () => {
  const before = room(); before.chapters = [{ id: 'b', title: 'b', pendingResourceTypes: ['report', 'quiz'], resources: [video('pending:b', false)] }];
  assert.deepEqual(withResourcePlaceholders(before).chapters[0].resources.map(r => r.kind), ['report', 'quiz']);
});
