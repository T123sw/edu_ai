import { test } from 'node:test';
import assert from 'node:assert/strict';
import { refreshLearningState, type LiveLearningState } from './stateRefresh';
import { apiRequest } from '../stitch/api/client';

test('refreshing one course avoids reading the full account and still refreshes background jobs', async () => {
  const old = { id: 'other' }, active = { id: 'course /1' };
  const snapshot = { rooms: [old, active], resources: ['preserved'], serverJobs: [] } as unknown as LiveLearningState;
  const calls: string[] = [];
  const request = (async (path: string) => {
    calls.push(path);
    if (path === '/api/jobs?limit=100') return { items: [{ edu_job_id: 'j', status: 'running', course_id: null, message: null }] };
    return { id: active.id, title: 'updated' };
  }) as typeof apiRequest;
  const result = await refreshLearningState(snapshot, active.id, request);
  assert.deepEqual(calls.sort(), ['/api/jobs?limit=100', '/api/self-learning/courses/course%20%2F1']);
  assert.equal(result.rooms[0], old);
  assert.equal(result.rooms[1].title, 'updated');
  assert.equal(result.resources, snapshot.resources);
  assert.equal(result.serverJobs[0].status, 'running');
  assert.equal(result.serverJobs[0].course_id, undefined);
});

test('home and an unknown course load the complete state', async () => {
  for (const id of ['', 'new-course']) {
    const snapshot = { rooms: [] } as unknown as LiveLearningState;
    const request = (async (path: string) => { assert.equal(path, '/api/self-learning/state'); return snapshot; }) as typeof apiRequest;
    assert.equal(await refreshLearningState(snapshot, id, request), snapshot);
  }
});
