import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassroomQuizQuestion } from '../stitch/api/types.ts';
import {
  clearQuizDraft,
  gradeQuizQuestions,
  quizStorageKey,
  readQuizDraft,
  writeQuizDraft,
} from './quizScene.ts';

const questions: ClassroomQuizQuestion[] = [
  {
    id: 'single',
    type: 'single',
    question: '单选',
    answer: ['B'],
    points: 10,
  },
  {
    id: 'multiple',
    type: 'multiple',
    question: '多选',
    answer: ['A', 'C'],
    points: 15,
  },
  {
    id: 'short',
    type: 'short_answer',
    question: '简答',
    points: 20,
    hasAnswer: false,
  },
  {
    id: 'custom',
    type: 'matching',
    question: '未知题型',
    points: 5,
  },
];

test('grades objective questions and leaves short answers for self review', () => {
  const grade = gradeQuizQuestions(questions, {
    single: 'B',
    multiple: ['C', 'A'],
    short: '我的答案',
    custom: 'value',
  });

  assert.deepEqual(
    grade.results.map(({ questionId, status }) => ({ questionId, status })),
    [
      { questionId: 'single', status: 'correct' },
      { questionId: 'multiple', status: 'correct' },
      { questionId: 'short', status: 'self_review' },
      { questionId: 'custom', status: 'unsupported' },
    ],
  );
  assert.equal(grade.objectiveEarned, 25);
  assert.equal(grade.objectivePossible, 25);
});

test('marks incomplete or extra objective selections incorrect', () => {
  const grade = gradeQuizQuestions(questions.slice(0, 2), {
    multiple: ['A', 'B', 'C'],
  });

  assert.deepEqual(
    grade.results.map((result) => result.status),
    ['incorrect', 'incorrect'],
  );
  assert.equal(grade.objectiveEarned, 0);
  assert.equal(grade.objectivePossible, 25);
});

test('persists a versioned quiz draft and removes malformed recovery data', () => {
  const values = new Map<string, string>();
  const removed: string[] = [];
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => {
      removed.push(key);
      values.delete(key);
    },
  };
  const key = quizStorageKey('course/a', 'classroom b', 'scene#1');

  writeQuizDraft(storage, key, {
    answers: { single: 'B', multiple: ['A', 'C'] },
    submitted: true,
  });
  assert.deepEqual(readQuizDraft(storage, key), {
    answers: { single: 'B', multiple: ['A', 'C'] },
    submitted: true,
  });

  values.set(key, '{bad json');
  assert.deepEqual(readQuizDraft(storage, key), {
    answers: {},
    submitted: false,
  });
  assert.deepEqual(removed, [key]);

  clearQuizDraft(storage, key);
  assert.deepEqual(removed, [key, key]);
  assert.equal(
    key,
    'edu-ai:classroom-quiz:v1:course%2Fa:classroom%20b:scene%231',
  );
});
