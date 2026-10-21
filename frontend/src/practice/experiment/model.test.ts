import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { start, transition, matches, type Spec, type Adapter } from './model';
const fixture = (name: string): Spec => JSON.parse(readFileSync(new URL(`../../../../backend/src/app/practice/skills/design-experiment/examples/${name}.json`, import.meta.url), 'utf8'));
const apply: Adapter['apply'] = (s, c) => ({ ...s, selected: c.input.index });
async function guided(spec: Spec, adapter = apply) { const initial = start(spec, 'a'.repeat(64)); const demo = await transition(spec, initial, { type: 'next' }, adapter); return transition(spec, demo, { type: 'phase', phase: 'guided' }, adapter); }
test('demo restricts manual actions; system operations do not imply mastery', async () => {
  const spec = fixture('quicksort'), initial = start(spec, 'a'.repeat(64));
  await assert.rejects(transition(spec, initial, { type: 'action', command: { action: 'select', input: { index: 4 } } }, apply), /不允许/);
  await assert.rejects(transition(spec, initial, { type: 'phase', phase: 'guided' }, apply), /完成演示/);
  const demo = await transition(spec, initial, { type: 'next' }, apply);
  assert.equal(demo.events[0].actor, 'system'); assert.equal(demo.verdict, ''); assert.equal(initial.state.selected, -1);
  assert.deepEqual((await transition(spec, demo, { type: 'back' }, apply)).state, initial.state);
});
test('wrong action preserves evidence and retries; correct action advances automatically', async () => {
  const spec = fixture('quicksort'), first = await guided(spec);
  const wrong = await transition(spec, first, { type: 'action', command: { action: 'select', input: { index: 2 } } }, apply);
  assert.equal(wrong.index, 0); assert.equal(wrong.verdict, 'fail'); assert.equal(wrong.state.selected, -1); assert.notEqual(wrong.attempt_id, first.attempt_id);
  const evidence = wrong.events.find(e => e.type === 'attempt_submitted')!;
  assert.equal(wrong.snapshots[evidence.after].selected, 2); assert.equal(evidence.attempt_id, first.attempt_id);
  const right = await transition(spec, wrong, { type: 'action', command: { action: 'select', input: { index: 4 } } }, apply);
  assert.equal(right.index, 1); assert.equal(right.verdict, 'pass'); assert.equal(right.state.selected, 4);
  await assert.rejects(transition(spec, first, { type: 'next' }, apply), /没有下一步/);
});
test('explicit submission groups multiple actions into one attempt', async () => {
  const spec = fixture('quicksort'); spec.tasks[0].submission = 'explicit_submit'; spec.tasks[0].submit_action = null;
  let v = await guided(spec);
  v = await transition(spec, v, { type: 'action', command: { action: 'select', input: { index: 2 } } }, apply); assert.equal(v.verdict, ''); assert.equal(v.state.selected, 2);
  v = await transition(spec, v, { type: 'action', command: { action: 'select', input: { index: 4 } } }, apply);
  v = await transition(spec, v, { type: 'submit' }, apply); assert.equal(v.verdict, 'pass');
  assert.equal(v.events.filter(e => e.type === 'attempt_submitted').length, 1);
});
test('rubric awaits review, explore stays available without awarding success', async () => {
  const spec = fixture('quicksort'); spec.tasks[0].assessment = 'rubric'; spec.tasks[0].rubric = ['解释基准选择'];
  const v = await transition(spec, await guided(spec), { type: 'action', command: { action: 'select', input: { index: 4 } } }, apply);
  assert.equal(v.verdict, 'awaiting_review'); assert.equal(v.index, 0);
  const explore = await transition(spec, v, { type: 'phase', phase: 'explore' }, apply); assert.equal(explore.verdict, ''); assert.equal(explore.state.selected, -1);
});
test('mechanics and stochastic simulation use the same interpreter', async () => {
  const cases: [string, Adapter['apply']][] = [
    ['friction', (s, c) => ({ ...s, mu: c.input.mu, distance: Number(s.velocity) ** 2 / (2 * Number(c.input.mu) * 9.8) })],
    ['probability', (s, c) => { let seed = Number(s.seed); const samples: number[] = []; for (let i = 0; i < Number(c.input.count); i++) { seed = (seed * 1664525 + 1013904223) >>> 0; samples.push(seed / 2 ** 32 < .5 ? 1 : 0); } return { ...s, seed, samples, count: samples.length, frequency: samples.reduce((a, b) => a + b, 0) / samples.length }; }],
  ];
  for (const [name, adapter] of cases) {
    const spec = fixture(name), result = await transition(spec, await guided(spec, adapter), { type: 'action', command: spec.validation_cases[0].commands[0] }, adapter);
    assert.equal(result.verdict, 'pass', name); if (name === 'probability') assert.notEqual(result.state.frequency, .5);
  }
});
test('invalid inputs, nonfinite state and failing demos do not mutate state', async () => {
  const spec = fixture('quicksort'), v = await guided(spec);
  await assert.rejects(transition(spec, v, { type: 'action', command: { action: 'select', input: { index: 99 } } }, apply), /范围/);
  await assert.rejects(transition(spec, v, { type: 'action', command: { action: 'select', input: { index: 4 } } }, () => ({ selected: NaN })), /有限/);
  await assert.rejects(transition(spec, start(spec, 'a'.repeat(64)), { type: 'next' }, s => s), /未通过/); assert.equal(v.state.selected, -1);
});
test('tolerance and missing paths are judged without eval', () => {
  const ctx = { before: {}, after: { x: .30000001 }, input: {} };
  assert.equal(matches({ path: ['after','x'], op: 'near', value: .3, tolerance: .000001 }, ctx), true);
  assert.equal(matches({ path: ['after','missing'], op: 'ne', value: 0, tolerance: 0 }, ctx), false);
});
test('missing evidence does not mark a learner wrong', async () => {
  const spec = fixture('quicksort'); spec.tasks[0].checks[0].path = ['after','unavailable'];
  const v = await transition(spec, await guided(spec), { type: 'action', command: { action: 'select', input: { index: 4 } } }, apply);
  assert.equal(v.verdict, 'unknown'); assert.equal(v.index, 0); assert.equal(v.events.some(e => e.type === 'retry_started'), false);
});
