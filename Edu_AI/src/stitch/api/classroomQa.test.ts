import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import {
  buildClassroomQaSessionPath,
  buildClassroomQaTurnsPath,
  fetchClassroomQaAudioBlobUrl,
} from './classroomQa.ts';

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalCreateObjectUrl = URL.createObjectURL;

afterEach(() => {
  globalThis.fetch = originalFetch;
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: originalWindow,
  });
  URL.createObjectURL = originalCreateObjectUrl;
});

test('classroom QA paths encode course and classroom identifiers', () => {
  assert.equal(
    buildClassroomQaSessionPath('course / 一', 'classroom?#'),
    '/api/courses/course%20%2F%20%E4%B8%80/classrooms/classroom%3F%23/qa/session',
  );
  assert.equal(
    buildClassroomQaTurnsPath('course / 一', 'classroom?#'),
    '/api/courses/course%20%2F%20%E4%B8%80/classrooms/classroom%3F%23/qa/turns',
  );
});

test('authenticated audio fetch creates an object URL only after success', async () => {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      localStorage: {
        getItem: () => JSON.stringify({ token: 'student-token' }),
      },
    },
  });
  let authorization = '';
  globalThis.fetch = async (_input, init) => {
    authorization = new Headers(init?.headers).get('Authorization') ?? '';
    return new Response(new Blob(['audio']), { status: 200 });
  };
  let created = 0;
  URL.createObjectURL = () => {
    created += 1;
    return 'blob:answer';
  };

  const result = await fetchClassroomQaAudioBlobUrl('/api/audio/answer.mp3');

  assert.equal(result, 'blob:answer');
  assert.equal(authorization, 'Bearer student-token');
  assert.equal(created, 1);

  globalThis.fetch = async () => new Response('missing', { status: 404 });
  await assert.rejects(
    fetchClassroomQaAudioBlobUrl('/api/audio/missing.mp3'),
  );
  assert.equal(created, 1);
});
