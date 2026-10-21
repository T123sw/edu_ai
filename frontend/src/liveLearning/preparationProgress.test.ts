import assert from 'node:assert/strict';
import test from 'node:test';
import { mergePreparationTasks, preparationStepIndex, preparationJob, preparationGlobalJob, preparationFailure, type PreparationTask } from './preparationProgress';
import { buildJobCourseGroups } from '../jobs/jobCourseGrouping';
import { createJobStore } from '../jobs/jobStore';

test('historical error codes become readable reasons and unknown errors remain private', () => {
  for (const [code, expected] of [['CONTEXT_BUDGET_EXCEEDED', '单次处理上限'], ['DEADLINE_EXCEEDED', '时间上限'],
    ['BUDGET_EXHAUSTED:cost_micro_usd', '生成额度'], ['MODEL_UNAVAILABLE', '响应超时'], ['SECRET STACK TRACE', '没有足够信息']]) {
    const task: PreparationTask = { preparation_id: 'p', status: 'failed', stage: 'produce', revision: 1, error_code: code };
    assert.ok(preparationFailure(task).reason.includes(expected));
    assert.ok(!JSON.stringify(preparationFailure(task)).includes(code));
    assert.equal(preparationJob(task).error_message, preparationFailure(task).reason);
  }
});

test('structured failure details retain saved progress and every resource issue', () => {
  const failure = { ...preparationFailure({ error_code: 'CONTEXT_BUDGET_EXCEEDED' }), saved_resources: 4,
    planned_resources: 12, resource_issues: [{ resource_title: '快速排序', resource_type: 'AI 课堂', step: '制作课堂', reason: '页面内容过多' }] };
  assert.deepEqual(preparationFailure({ failure }), failure);
});

test('a late poll cannot roll a retried or completed task back to an old revision', () => {
  const current: PreparationTask = { preparation_id: 'p', status: 'succeeded', stage: 'commit', revision: 9, result_ref: { course_ready: true, course_id: 'c' } };
  const result = mergePreparationTasks([current], [{ ...current, status: 'running', stage: 'produce', revision: 7 }]);
  assert.equal(result[0].status, 'succeeded');
  assert.equal(preparationStepIndex(result[0]), 5);
});

test('global center includes uncommitted preparations and refuses stale status after retry', () => {
  const failed: PreparationTask = { preparation_id: 'p', status: 'failed', stage: 'review', revision: 244, created_at: '2026-10-15T10:00:00Z' };
  assert.equal(preparationJob(failed).created_at, failed.created_at);
  assert.equal(preparationGlobalJob(failed, 'alice').created_at, failed.created_at);
  const store = createJobStore();
  store.getState().mergeJobs([preparationGlobalJob(failed, 'alice')]);
  store.getState().mergeJobs([preparationGlobalJob({ ...failed, status: 'checking', revision: 245 }, 'alice')]);
  store.getState().mergeJobs([preparationGlobalJob(failed, 'alice')]);
  assert.equal(store.getState().activeCount, 1);
  const groups = buildJobCourseGroups(Object.values(store.getState().jobs), { currentCourseId: 'another-course', courseTitles: new Map() });
  assert.equal(groups.at(-1)?.jobs[0].preparation?.revision, 245);
});

test('repair can return to content generation and unknown stages do not imply completion', () => {
  const task: PreparationTask = { preparation_id: 'p', status: 'running', stage: 'repair', revision: 8 };
  assert.equal(preparationStepIndex(task), 3);
  assert.equal(preparationStepIndex({ ...task, stage: 'produce' }), 2);
  assert.equal(preparationStepIndex({ ...task, stage: 'future_stage' }), -1);
  assert.equal(preparationJob(task).progress, undefined);
  assert.equal(preparationJob({ ...task, status: 'accepted' }).status, 'queued');
});

test('partial delivery has a course link without pretending the whole course succeeded', () => {
  const task: PreparationTask = { preparation_id: 'p', status: 'failed', stage: 'review', revision: 10,
    result_ref: { course_ready: false, course_available: true, course_id: 'course-p', available_resources: 11, planned_resources: 12 } };
  const job = preparationJob(task);
  assert.equal(job.status, 'partially_succeeded');
  assert.equal(job.course_id, 'course-p');
  assert.match(job.message || '', /可以先学习/);
  assert.equal(preparationStepIndex(task), 3);
  assert.equal(preparationJob({ ...task, status: 'running' }).status, 'running');
});
