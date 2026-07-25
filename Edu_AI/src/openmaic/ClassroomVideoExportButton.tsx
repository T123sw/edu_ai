import { useRef, useState } from 'react';
import {
  downloadClassroomVideoArtifact,
  exportClassroomVideo,
  getJobStatus,
} from '../stitch/api/classroom';
import { waitForVideoExportJob, type VideoExportResultRef } from './videoExportJob';

export interface ClassroomVideoExportButtonProps {
  courseId: string;
  classroomId: string;
  title: string;
}

function safeFilename(title: string, extension: string): string {
  const stem =
    title
      .trim()
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
      .replace(/[.\s]+$/g, '')
      .slice(0, 96) || '课堂视频';
  return `${stem}.${extension}`;
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function ClassroomVideoExportButton({
  courseId,
  classroomId,
  title,
}: ClassroomVideoExportButtonProps) {
  const running = useRef(false);
  const [exporting, setExporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<VideoExportResultRef | null>(null);

  async function download(path: string, extension: string): Promise<void> {
    const blob = await downloadClassroomVideoArtifact(path);
    if (blob.size === 0) throw new Error('导出文件为空');
    saveBlob(blob, safeFilename(title, extension));
  }

  async function handleExport(): Promise<void> {
    if (running.current) return;
    running.current = true;
    setExporting(true);
    setResult(null);
    setProgress(0);
    setStatus('正在提交视频导出任务…');
    try {
      const initial = await exportClassroomVideo(courseId, classroomId);
      const completed = await waitForVideoExportJob(initial, {
        getStatus: getJobStatus,
        onProgress: (job) => {
          setProgress(job.progress);
          setStatus(job.message || `正在导出视频（${job.progress}%）`);
        },
      });
      setResult(completed);
      await download(completed.video_url, 'mp4');
      setStatus('MP4 已开始下载');
    } catch (error) {
      setStatus(error instanceof Error ? `导出失败：${error.message}` : '导出失败，请重试');
    } finally {
      running.current = false;
      setExporting(false);
    }
  }

  async function handleSubtitleDownload(): Promise<void> {
    if (!result?.subtitle_url) return;
    try {
      await download(result.subtitle_url, 'srt');
      setStatus('SRT 字幕已开始下载');
    } catch (error) {
      setStatus(error instanceof Error ? `字幕下载失败：${error.message}` : '字幕下载失败');
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={handleExport}
        disabled={exporting}
        aria-busy={exporting}
        className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
      >
        <span aria-hidden="true">▶</span>
        {exporting ? `导出视频 ${progress}%` : '导出 MP4'}
      </button>
      {result?.subtitle_url ? (
        <button
          type="button"
          onClick={handleSubtitleDownload}
          className="rounded-full border border-(--shell-border) bg-white px-3 py-2 text-xs font-bold text-(--accent-strong)"
        >
          下载 SRT
        </button>
      ) : null}
      <span role="status" aria-live="polite" className="max-w-64 text-xs text-(--muted-text)">
        {status}
      </span>
    </div>
  );
}
