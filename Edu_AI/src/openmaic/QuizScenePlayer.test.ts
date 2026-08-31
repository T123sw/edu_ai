import assert from 'node:assert/strict';
import test from 'node:test';

import type { ClassroomQuizQuestion } from '../stitch/api/types';
import { buildResourceQuestionSubmission } from './quizScene';


const questions: ClassroomQuizQuestion[] = [
  { id: 'q1', type: 'single', question: 'one', required: true },
  { id: 'q2', type: 'short_answer', question: 'two', required: true },
];

test('quiz submission persists all non-empty answers even when every answer is wrong', () => {
  const payload = buildResourceQuestionSubmission(questions, {
    q1: 'wrong',
    q2: 'still wrong',
  });

  assert.deepEqual(Object.keys(payload.answers), ['q1', 'q2']);
});

test('quiz submission rejects a missing required answer', () => {
  assert.throws(
    () => buildResourceQuestionSubmission(questions, { q1: 'A' }),
    /请完成所有必答题/,
  );
});

