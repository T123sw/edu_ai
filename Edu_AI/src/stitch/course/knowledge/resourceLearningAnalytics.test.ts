import assert from 'node:assert/strict';
import test from 'node:test';

import { resourceLearningQueueLabel } from './resourceLearningAnalyticsPresentation';

test('teacher queues keep coverage and question blockers separate', () => {
  assert.equal(
    resourceLearningQueueLabel('coverage_ready_questions_pending'),
    '讲解已达标，习题待完成',
  );
  assert.equal(
    resourceLearningQueueLabel('questions_ready_coverage_pending'),
    '习题已完成，讲解待学习',
  );
});
