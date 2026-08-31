import assert from 'node:assert/strict';
import test from 'node:test';

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

