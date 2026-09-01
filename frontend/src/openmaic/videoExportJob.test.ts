import assert from 'node:assert/strict';
import test from 'node:test';
import type { EduJob } from '../stitch/api/types.ts';
import { waitForVideoExportJob } from './videoExportJob.ts';

function job(
  status: EduJob['status'],
  overrides: Partial<EduJob> = {},
): EduJob {
  return {
    edu_job_id: 'job-video-1',
    kind: 'render_video',
    status,
    step: status,
    progress: status === 'succeeded' ? 100 : status === 'queued' ? 0 : 20,
    message: '',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

test('waitForVideoExportJob reports progress and returns the video result', async () => {
  const states = [
    job('running', { step: 'recording', progress: 30 }),
    job('running', { step: 'mixing', progress: 85 }),
    job('succeeded', {
      result_ref: {
        course_id: 'course-1',
        classroom_id: 'classroom-1',
        video_url: '/video/classroom.mp4',
        subtitle_url: '/video/classroom.srt',
        timeline_url: '/video/timeline.json',
        duration_ms: 5000,
        scene_count: 2,
      },
    }),
  ];
  const progress: number[] = [];
  const result = await waitForVideoExportJob(job('queued'), {
    getStatus: async () => states.shift()!,
    sleep: async () => undefined,
    onProgress: (current) => progress.push(current.progress),
  });

  assert.equal(result.video_url, '/video/classroom.mp4');
  assert.deepEqual(progress, [0, 30, 85, 100]);
});

test('waitForVideoExportJob surfaces backend failures', async () => {
  await assert.rejects(
    waitForVideoExportJob(job('queued'), {
      getStatus: async () =>
        job('failed', {
          error: 'ffmpeg unavailable',
          error_code: 'VIDEO_EXPORT_FAILED',
        }),
      sleep: async () => undefined,
    }),
    /ffmpeg unavailable/,
  );
});

test('waitForVideoExportJob rejects a success without video artifacts', async () => {
  await assert.rejects(
    waitForVideoExportJob(job('succeeded'), {
      getStatus: async () => job('succeeded'),
      sleep: async () => undefined,
    }),
    /completed without a video result/,
  );
});
