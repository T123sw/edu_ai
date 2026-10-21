import test from 'node:test';
import assert from 'node:assert/strict';
import { createLesson, createPrototype, reduceLesson, reducePrototype, type Lesson } from './bubbleSort';
import { restorePrototype } from '../prototypeStorage';
const algorithm = (s: Lesson) => ({ items: s.items, cursor: s.cursor, round: s.round, comparisons: s.comparisons, swaps: s.swaps, mode: s.mode });
const pair = (s: Lesson, index: number) => reduceLesson(reduceLesson(s, { type: 'select', index }, 'practice'), { type: 'select', index: index + 1 }, 'practice');

test('demonstration separates comparison and mutation, then teaches keeping the order', () => {
  let s = createLesson('demo');
  const initial = s.items.map(x => x.value);
  s = reduceLesson(s, { type: 'compare' }, 'demo');
  assert.deepEqual(s.items.map(x => x.value), initial); assert.equal(s.comparisons, 1);
  const before = algorithm(s);
  s = reduceLesson(s, { type: 'compare' }, 'demo'); assert.deepEqual(algorithm(s), before);
  s = reduceLesson(s, { type: 'decide', swap: true }, 'demo');
  assert.deepEqual(s.items.map(x => x.value), [3, 5, 4, 1]);
  for (let i = 0; i < 2; i++) { s = reduceLesson(s, { type: 'compare' }, 'demo'); s = reduceLesson(s, { type: 'decide', swap: true }, 'demo'); }
  assert.equal(s.mode, 'round-end'); assert.deepEqual(s.items.map(x => x.value), [3, 4, 1, 5]);
  assert.equal(s.comparisons, 3); assert.equal(s.swaps, 3);
  s = reduceLesson(s, { type: 'keep-example' }, 'demo'); s = reduceLesson(s, { type: 'compare' }, 'demo');
  s = reduceLesson(s, { type: 'decide', swap: false }, 'demo');
  assert.equal(s.mode, 'done'); assert.equal(s.comparisons, 4); assert.equal(s.swaps, 3);
});

test('wrong objects, wrong decisions, and an early round claim preserve algorithm state', () => {
  const cases = [
    (s: Lesson) => reduceLesson(s, { type: 'finish-round' }, 'practice'),
    (s: Lesson) => reduceLesson(s, { type: 'compare' }, 'practice'),
    (s: Lesson) => reduceLesson(s, { type: 'keep-example' }, 'practice'),
    (s: Lesson) => reduceLesson(pair(s, 1), { type: 'decide', swap: true }, 'practice'),
    (s: Lesson) => reduceLesson(pair(s, 0), { type: 'decide', swap: false }, 'practice'),
    (s: Lesson) => reduceLesson(reduceLesson(reduceLesson(s, { type: 'select', index: 0 }, 'practice'), { type: 'select', index: 2 }, 'practice'), { type: 'decide', swap: true }, 'practice'),
  ];
  for (const run of cases) { const s = createLesson('practice'), result = run(s); assert.deepEqual(algorithm(result), algorithm(s)); assert.equal(result.feedback.kind, 'error'); }
});

test('two manual rounds require explicit declarations and yield independently known counts', () => {
  let s = createLesson('practice');
  const expected = [[1, 4, 2, 5, 3, 8], [1, 2, 4, 3, 5, 8]];
  for (let round = 0; round < 2; round++) {
    for (let index = 0; index < 5 - round; index++) {
      const swap = s.items[index].value > s.items[index + 1].value;
      s = reduceLesson(pair(s, index), { type: 'decide', swap }, 'practice');
      assert.deepEqual(s.selected, []); // Never preselect the next pair for the learner.
    }
    assert.equal(s.round, round); assert.equal(s.mode, 'round-end');
    assert.deepEqual(s.items.map(x => x.value), expected[round]);
    s = reduceLesson(s, { type: 'finish-round' }, 'practice');
  }
  assert.equal(s.mode, 'done'); assert.equal(s.comparisons, 9); assert.equal(s.swaps, 6);
  assert.match(s.feedback.explanation, /不等于整个数组排好/);
});

test('each round puts its maximum in place while preserving duplicate identities and negative values', () => {
  for (const values of [[-1, -4, 0, -1, 2], [5, 4, 3, 2, 1], [1, 2, 3, 4], [2, 2, 2, 2]]) {
    let s = createLesson('practice', values); const original = s.items;
    for (let round = 0; round < 2; round++) {
      const end = values.length - 1 - round, max = Math.max(...s.items.slice(0, end + 1).map(x => x.value));
      for (let index = 0; index < end; index++) s = reduceLesson(pair(s, index), { type: 'decide', swap: s.items[index].value > s.items[index + 1].value }, 'practice');
      assert.equal(s.items[end].value, max); s = reduceLesson(s, { type: 'finish-round' }, 'practice');
    }
    assert.deepEqual([...s.items].sort((a, b) => a.id.localeCompare(b.id)), [...original].sort((a, b) => a.id.localeCompare(b.id)));
    for (const value of new Set(values)) assert.deepEqual(s.items.filter(x => x.value === value).map(x => x.id), original.filter(x => x.value === value).map(x => x.id));
  }
});

test('hints become more specific without performing any action', () => {
  let s = createLesson('practice'); const before = algorithm(s);
  for (let i = 1; i <= 3; i++) { s = reduceLesson(s, { type: 'hint' }, 'practice'); assert.equal(s.hintLevel, i); assert.deepEqual(algorithm(s), before); assert.deepEqual(s.selected, []); }
  assert.match(s.feedback.explanation, /5 > 1/); assert.equal(s.hints, 3);
});

test('phase switching and retry keep independent learning states', () => {
  let s = createPrototype(); s = reducePrototype(s, { type: 'compare' }); const demo = s.demo;
  s = reducePrototype(s, { type: 'phase', phase: 'practice' }); s = reducePrototype(s, { type: 'select', index: 0 });
  const practice = s.practice; s = reducePrototype(s, { type: 'phase', phase: 'demo' }); assert.deepEqual(s.demo, demo);
  s = reducePrototype(s, { type: 'reset' }); assert.deepEqual(s.practice, practice); assert.equal(s.demo.comparisons, 0);
});

test('saved actions reconstruct actual state; malformed storage starts safely with a notice', () => {
  const actions = [{ type: 'phase', phase: 'practice' }, { type: 'select', index: 0 }, { type: 'select', index: 1 }, { type: 'decide', swap: true }];
  const restored = restorePrototype(JSON.stringify({ version: 1, actions }));
  assert.equal(restored.state.practice.comparisons, 1); assert.deepEqual(restored.state.practice.items.map(x => x.value), [1, 5, 4, 2, 8, 3]);
  for (const raw of ['{', JSON.stringify({ version: 1, actions: [{ type: 'phase', phase: 'oops' }] }), JSON.stringify({ version: 1, actions: [{ type: 'decide', swap: 'true' }] })]) {
    const invalid = restorePrototype(raw); assert.ok(invalid.warning); assert.deepEqual(invalid.state, createPrototype());
  }
});
