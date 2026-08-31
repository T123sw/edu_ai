import assert from 'node:assert/strict';
import test from 'node:test';

import type { ResourceLearningProgress } from '../../api/types';
import {
  buildStudentClassroomLearningHref,
  resourceLearningLabels,
} from './resourceLearningPresentation';

function progress(
  overrides: Partial<ResourceLearningProgress> = {},
): ResourceLearningProgress {
  return {
    course_id: 'course-1',
    resource_id: 'classroom-1',
    resource_version: 3,
    status: 'completed',
    explanation_covered_ms: 830,
    explanation_total_ms: 1_000,
    explanation_coverage_percent: 83,
    required_question_count: 3,
    answered_question_count: 3,
    question_completion_percent: 100,
    correct_count_first: 0,
    correct_count_latest: 0,
    demo_view_count: 0,
    demo_interaction_count: 0,
    started_at: null,
    completed_at: '2026-08-31T08:00:00Z',
    last_activity_at: null,
    updated_at: '2026-08-31T08:00:00Z',
    ...overrides,
  };
}

test('student classroom link carries the approved resource version', () => {
  assert.equal(
    buildStudentClassroomLearningHref('course-1', 'classroom-1', 3),
    '#classroom-player?course_id=course-1&classroom_id=classroom-1&resource_version=3',
  );
});

test('progress copy keeps coverage and questions separate', () => {
  assert.deepEqual(resourceLearningLabels(progress()), {
    coverage: '讲解完整度 83%',
    questions: '习题进度 3/3',
    status: '已完成',
  });
});

test('behavior-only resources never claim completion', () => {
  assert.equal(
    resourceLearningLabels(
      progress({ manifest: { manifest_id: 'm1', resource_version: 3, content_hash: 'h', mode: 'behavior_only', scenes: [], required_question_ids: [] } }),
    ).status,
    '已记录学习行为',
  );
});
