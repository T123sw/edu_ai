import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

import { shouldTrackResourceLearning } from './classroomResourceLearning';


test('resource learning activates only for a student with an exact approved version', () => {
  assert.equal(
    shouldTrackResourceLearning({ role: 'student', courseRole: 'viewer', resourceVersion: 3 }),
    true,
  );
  assert.equal(
    shouldTrackResourceLearning({ role: 'teacher', courseRole: 'owner', resourceVersion: 3 }),
    false,
  );
  assert.equal(
    shouldTrackResourceLearning({ role: 'student', courseRole: 'viewer', resourceVersion: null }),
    false,
  );
});

test('student reading and practice use explicit server learning evidence', async () => {
  const source = (name: string) => readFile(new URL(`../course/classroomCatalog/${name}`, import.meta.url), 'utf8');
  const [reading, practice, viewer] = await Promise.all([
    source('StudentReadingView.tsx'),
    source('StudentPracticeView.tsx'),
    source('CourseResourceViewer.tsx'),
  ]);
  assert.match(reading, /recordReadingActivity/);
  assert.match(reading, /"opened"/);
  assert.match(reading, /完成阅读/);
  assert.doesNotMatch(reading, /setTimeout|elapsed|duration/);
  assert.match(practice, /getQuizQuestions/);
  assert.match(practice, /submitResourceQuestions/);
  assert.match(practice, /required/);
  assert.match(viewer, /StudentReadingView/);
  assert.match(viewer, /StudentPracticeView/);
});
