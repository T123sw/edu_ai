import { test } from 'node:test';
import assert from 'node:assert/strict';
import { startRound, reviewCard, studyCards } from './round';

test('known cards leave the round; uncertain cards return after the others', () => {
  let state = startRound(3);
  state = reviewCard(state, true);
  assert.deepEqual(state.remaining, [1, 2]);
  state = reviewCard(state, false);
  assert.deepEqual(state.remaining, [2, 1]);
  state = reviewCard(state, true);
  state = reviewCard(state, false);
  assert.deepEqual(state.remaining, [1]);
  assert.equal(state.known, 2);
  state = reviewCard(state, true);
  assert.deepEqual(state, { remaining: [], known: 3, attempts: 5 });
  assert.equal(reviewCard(state, false), state);
  assert.deepEqual(startRound(3).remaining, [0, 1, 2]);
});
test('legacy card fields normalize and empty entries are not studied', () => {
  assert.deepEqual(studyCards([null, {}, { front: '问题', back: '答案' }, { question: 'Q', answer: 'A' }]), [{ front: '问题', back: '答案' }, { front: 'Q', back: 'A' }]);
});
