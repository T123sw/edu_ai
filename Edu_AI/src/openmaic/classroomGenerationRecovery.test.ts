import assert from 'node:assert/strict';
import test from 'node:test';
import type { EduJob } from '../stitch/api/types.ts';
import {
  clearPendingClassroomGeneration,
  readPendingClassroomGeneration,
  savePendingClassroomGeneration,
} from './classroomGenerationRecovery.ts';

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

function job(id: string, progress = 20): EduJob {
  return {
    edu_job_id: id,
    kind: 'generate_classroom',
    status: 'running',
    step: 'generating_scenes',
    progress,
    message: '',
    created_at: '2026-07-26T00:00:00Z',
    updated_at: '2026-07-26T00:01:00Z',
  };
}

test('saves and restores the latest classroom job for a course', () => {
  const storage = new MemoryStorage();
  savePendingClassroomGeneration(storage, {
    courseId: 'course-1',
    topic: '快速排序',
    job: job('job-1', 42),
    savedAt: '2026-07-26T00:02:00Z',
  });

  assert.deepEqual(readPendingClassroomGeneration(storage, 'course-1'), {
    courseId: 'course-1',
    topic: '快速排序',
    job: job('job-1', 42),
    savedAt: '2026-07-26T00:02:00Z',
  });
});

test('keeps pending classroom jobs isolated by course', () => {
  const storage = new MemoryStorage();
  savePendingClassroomGeneration(storage, {
    courseId: 'course-1',
    topic: '主题一',
    job: job('job-1'),
    savedAt: 'one',
  });
  savePendingClassroomGeneration(storage, {
    courseId: 'course-2',
    topic: '主题二',
    job: job('job-2'),
    savedAt: 'two',
  });

  assert.equal(
    readPendingClassroomGeneration(storage, 'course-1')?.job.edu_job_id,
    'job-1',
  );
  assert.equal(
    readPendingClassroomGeneration(storage, 'course-2')?.job.edu_job_id,
    'job-2',
  );
});

test('a newer job replaces the previous job for the same course', () => {
  const storage = new MemoryStorage();
  savePendingClassroomGeneration(storage, {
    courseId: 'course-1',
    topic: '旧主题',
    job: job('job-old'),
    savedAt: 'old',
  });
  savePendingClassroomGeneration(storage, {
    courseId: 'course-1',
    topic: '新主题',
    job: job('job-new'),
    savedAt: 'new',
  });

  assert.equal(
    readPendingClassroomGeneration(storage, 'course-1')?.job.edu_job_id,
    'job-new',
  );
});

test('an old poll cannot clear a newer job for the same course', () => {
  const storage = new MemoryStorage();
  savePendingClassroomGeneration(storage, {
    courseId: 'course-1',
    topic: '新主题',
    job: job('job-new'),
    savedAt: 'new',
  });

  clearPendingClassroomGeneration(storage, 'course-1', 'job-old');
  assert.equal(
    readPendingClassroomGeneration(storage, 'course-1')?.job.edu_job_id,
    'job-new',
  );

  clearPendingClassroomGeneration(storage, 'course-1', 'job-new');
  assert.equal(readPendingClassroomGeneration(storage, 'course-1'), null);
});

test('ignores malformed recovery data', () => {
  const storage = new MemoryStorage();
  storage.setItem('edu-ai-pending-classroom-generations-v1', '{bad json');

  assert.equal(readPendingClassroomGeneration(storage, 'course-1'), null);
});
