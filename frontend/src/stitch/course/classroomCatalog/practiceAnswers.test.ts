import assert from 'node:assert/strict';
import test from 'node:test';
import { isMultipleChoice, practiceOptionValue } from './practiceAnswers';
test('unlabelled option text submits canonical answer letters', () => {
  assert.equal(practiceOptionValue('静止或匀速直线运动', 0), 'A');
  assert.equal(practiceOptionValue('加速运动', 1), 'B');
  assert.equal(practiceOptionValue('C、减速运动', 2), 'C');
  assert.equal(isMultipleChoice('multiple_choice'), true);
  assert.equal(isMultipleChoice('single_choice'), false);
});
