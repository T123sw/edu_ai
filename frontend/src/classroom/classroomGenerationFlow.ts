import type { EduJob } from '../stitch/api/types.ts';

export type ClassroomGenerationResultRef = NonNullable<EduJob['result_ref']> & {
  course_id: string;
  classroom_id: string;
};

export interface ClassroomGenerationDependencies {
  getStatus: (jobId: string) => Promise<EduJob>;
  sleep?: (durationMs: number) => Promise<void>;
  pollIntervalMs?: number;
  maxConsecutivePollErrors?: number;
  onProgress?: (job: EduJob) => void;
  signal?: AbortSignal;
}

function assertNotAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new Error('课堂生成已取消');
  }
}

function sleepWithAbort(durationMs: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    assertNotAborted(signal);

    const timer = globalThis.setTimeout(() => {
      signal?.removeEventListener('abort', handleAbort);
      resolve();
    }, durationMs);

    const handleAbort = () => {
      globalThis.clearTimeout(timer);
      reject(new Error('课堂生成已取消'));
    };

    signal?.addEventListener('abort', handleAbort, { once: true });
  });
}

export function buildClassroomPlayerHash(
  courseId: string,
  classroomId: string,
  options?: {
    resourceVersion?: number | null;
    catalogNodeId?: string | null;
    catalogResourceId?: string | null;
  },
): string {
  const params = new URLSearchParams({ course_id: courseId, classroom_id: classroomId });
  if (options?.resourceVersion) params.set("resource_version", String(options.resourceVersion));
  if (options?.catalogNodeId) params.set("catalog_node_id", options.catalogNodeId);
  if (options?.catalogResourceId) params.set("catalog_resource_id", options.catalogResourceId);
  return `#classroom-player?${params.toString()}`;
}

export async function waitForClassroomGenerationJob(
  initialJob: EduJob,
  dependencies: ClassroomGenerationDependencies,
): Promise<ClassroomGenerationResultRef> {
  const sleep =
    dependencies.sleep ??
    ((durationMs: number) => sleepWithAbort(durationMs, dependencies.signal));
  const maxConsecutivePollErrors = Math.max(
    1,
    dependencies.maxConsecutivePollErrors ?? 3,
  );
  let consecutivePollErrors = 0;
  let current = initialJob;
  dependencies.onProgress?.(current);

  while (current.status === 'queued' || current.status === 'running') {
    assertNotAborted(dependencies.signal);
    await sleep(dependencies.pollIntervalMs ?? 4000);
    assertNotAborted(dependencies.signal);

    try {
      current = await dependencies.getStatus(current.edu_job_id);
      consecutivePollErrors = 0;
      dependencies.onProgress?.(current);
    } catch (error) {
      assertNotAborted(dependencies.signal);
      consecutivePollErrors += 1;
      if (consecutivePollErrors >= maxConsecutivePollErrors) {
        throw error;
      }
    }
  }

  if (current.status === 'failed') {
    throw new Error(current.error || current.message || 'AI 课堂生成失败');
  }

  if (!current.result_ref?.course_id || !current.result_ref.classroom_id) {
    throw new Error('课堂生成完成但缺少课堂结果');
  }

  return current.result_ref as ClassroomGenerationResultRef;
}
