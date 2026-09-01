import type { EduJob } from '../stitch/api/types.ts';

export type VideoExportResultRef = NonNullable<EduJob['result_ref']> & {
  video_url: string;
};

export interface VideoExportJobDependencies {
  getStatus: (jobId: string) => Promise<EduJob>;
  sleep?: (durationMs: number) => Promise<void>;
  pollIntervalMs?: number;
  onProgress?: (job: EduJob) => void;
}

export async function waitForVideoExportJob(
  initialJob: EduJob,
  dependencies: VideoExportJobDependencies,
): Promise<VideoExportResultRef> {
  const sleep =
    dependencies.sleep ??
    ((durationMs: number) =>
      new Promise<void>((resolve) => window.setTimeout(resolve, durationMs)));
  let current = initialJob;
  dependencies.onProgress?.(current);

  while (current.status === 'queued' || current.status === 'running') {
    await sleep(dependencies.pollIntervalMs ?? 1000);
    current = await dependencies.getStatus(current.edu_job_id);
    dependencies.onProgress?.(current);
  }

  if (current.status === 'failed') {
    throw new Error(current.error || current.message || '课堂视频导出失败');
  }
  if (!current.result_ref?.video_url) {
    throw new Error('video export completed without a video result');
  }
  return current.result_ref as VideoExportResultRef;
}
