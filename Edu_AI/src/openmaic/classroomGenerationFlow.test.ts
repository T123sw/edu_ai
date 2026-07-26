import assert from 'node:assert/strict';
import test from 'node:test';
import type { EduJob } from '../stitch/api/types.ts';
import {
  buildClassroomPlayerHash,
  waitForClassroomGenerationJob,
} from './classroomGenerationFlow.ts';

function job(
  status: EduJob['status'],
  overrides: Partial<EduJob> = {},
): EduJob {
  return {
    edu_job_id: 'job-classroom-1',
    kind: 'generate_classroom',
    status,
    step: status,
    progress: status === 'succeeded' ? 100 : status === 'queued' ? 0 : 20,
    message: '',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

test('buildClassroomPlayerHash encodes course and classroom ids', () => {
  assert.equal(
    buildClassroomPlayerHash('course/一', 'classroom?二'),
    '#classroom-player?course_id=course%2F%E4%B8%80&classroom_id=classroom%3F%E4%BA%8C',
  );
});

test('waitForClassroomGenerationJob reports progress and returns the classroom result', async () => {
  const states = [
    job('running', { step: 'researching', progress: 30 }),
    job('running', { step: 'generating_scenes', progress: 75 }),
    job('succeeded', {
      result_ref: {
        course_id: 'course-1',
        classroom_id: 'classroom-1',
        scenes_count: 9,
      },
    }),
  ];
  const progress: number[] = [];
  const result = await waitForClassroomGenerationJob(job('queued'), {
    getStatus: async () => states.shift()!,
    sleep: async () => undefined,
    onProgress: (current) => progress.push(current.progress),
  });

  assert.equal(result.course_id, 'course-1');
  assert.equal(result.classroom_id, 'classroom-1');
  assert.deepEqual(progress, [0, 30, 75, 100]);
});

test('waitForClassroomGenerationJob continues after a transient poll failure', async () => {
  let calls = 0;
  const result = await waitForClassroomGenerationJob(job('queued'), {
    getStatus: async () => {
      calls += 1;
      if (calls === 1) {
        throw new Error('temporary network error');
      }
      return job('succeeded', {
        result_ref: {
          course_id: 'course-1',
          classroom_id: 'classroom-1',
        },
      });
    },
    sleep: async () => undefined,
  });

  assert.equal(calls, 2);
  assert.equal(result.classroom_id, 'classroom-1');
});

test('waitForClassroomGenerationJob stops after repeated poll failures', async () => {
  let calls = 0;

  await assert.rejects(
    waitForClassroomGenerationJob(job('queued'), {
      getStatus: async () => {
        calls += 1;
        throw new Error('network unavailable');
      },
      sleep: async () => undefined,
      maxConsecutivePollErrors: 3,
    }),
    /network unavailable/,
  );

  assert.equal(calls, 3);
});

test('waitForClassroomGenerationJob surfaces a failed generation job', async () => {
  await assert.rejects(
    waitForClassroomGenerationJob(
      job('failed', {
        error: '课件服务不可用',
        error_code: 'CLASSROOM_GENERATION_FAILED',
      }),
      {
        getStatus: async () => job('failed'),
        sleep: async () => undefined,
      },
    ),
    /课件服务不可用/,
  );
});

test('waitForClassroomGenerationJob rejects success without a classroom result', async () => {
  await assert.rejects(
    waitForClassroomGenerationJob(job('succeeded'), {
      getStatus: async () => job('succeeded'),
      sleep: async () => undefined,
    }),
    /课堂生成完成但缺少课堂结果/,
  );
});

test('waitForClassroomGenerationJob stops polling when aborted', async () => {
  const controller = new AbortController();
  controller.abort();

  await assert.rejects(
    waitForClassroomGenerationJob(job('queued'), {
      signal: controller.signal,
      getStatus: async () => job('running'),
      sleep: async () => undefined,
    }),
    /课堂生成已取消/,
  );
});
