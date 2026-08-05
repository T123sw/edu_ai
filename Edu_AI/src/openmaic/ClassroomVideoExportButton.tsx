import { useEffect, useMemo, useState } from "react";
import {
  downloadClassroomVideoArtifact,
  exportClassroomVideo,
} from "../stitch/api/classroom";
import {
  registerCreatedJob,
  useCourseJobs,
} from "../jobs/jobStore";
import { isActiveJob } from "../jobs/types";

export interface ClassroomVideoExportButtonProps {
  courseId: string;
  classroomId: string;
  title: string;
}

function safeFilename(title: string, extension: string): string {
  const stem =
    title
      .trim()
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
      .replace(/[.\s]+$/g, "")
      .slice(0, 96) || "课堂视频";
  return `${stem}.${extension}`;
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
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
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [downloading, setDownloading] = useState<"video" | "subtitle" | null>(
    null,
  );
  const [localStatus, setLocalStatus] = useState<string | null>(null);
  const videoJobs = useCourseJobs(courseId, "render_video");
  const matchingJobs = useMemo(
    () =>
      videoJobs.filter(
        (candidate) =>
          String(candidate.input_summary.classroom_id || "") === classroomId,
      ),
    [classroomId, videoJobs],
  );
  const job =
    matchingJobs.find(
      (candidate) => candidate.edu_job_id === selectedJobId,
    ) ??
    matchingJobs.find(isActiveJob) ??
    matchingJobs[0] ??
    null;
  const exporting = Boolean(job && isActiveJob(job));
  const videoUrl =
    job?.status === "succeeded" &&
    typeof job.result_ref?.video_url === "string"
      ? job.result_ref.video_url
      : null;
  const subtitleUrl =
    job?.status === "succeeded" &&
    typeof job.result_ref?.subtitle_url === "string"
      ? job.result_ref.subtitle_url
      : null;

  useEffect(() => {
    if (job && !isActiveJob(job)) setLocalStatus(null);
  }, [job?.edu_job_id, job?.status, job?.updated_at]);

  async function download(
    path: string,
    extension: string,
    kind: "video" | "subtitle",
  ): Promise<void> {
    setDownloading(kind);
    setLocalStatus(null);
    try {
      const blob = await downloadClassroomVideoArtifact(path);
      if (blob.size === 0) throw new Error("导出文件为空");
      saveBlob(blob, safeFilename(title, extension));
      setLocalStatus(extension === "mp4" ? "MP4 已开始下载" : "SRT 字幕已开始下载");
    } catch (error) {
      setLocalStatus(
        error instanceof Error ? `下载失败：${error.message}` : "下载失败，请重试",
      );
    } finally {
      setDownloading(null);
    }
  }

  async function handleExport(): Promise<void> {
    if (submitting || exporting) return;
    setSubmitting(true);
    setLocalStatus("正在提交视频导出任务…");
    try {
      const created = await exportClassroomVideo(courseId, classroomId);
      registerCreatedJob(created);
      setSelectedJobId(created.edu_job_id);
      setLocalStatus("任务已转到后台，可以离开本页");
    } catch (error) {
      setLocalStatus(
        error instanceof Error
          ? `导出失败：${error.message}`
          : "导出失败，请重试",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const status =
    localStatus ??
    (exporting
      ? job?.message || `正在导出视频（${job?.progress ?? 0}%）`
      : job?.status === "failed"
        ? `导出失败：${job.error_message || job.error || "请在任务中心重试"}`
        : job?.status === "canceled"
          ? "视频导出已取消"
          : videoUrl
            ? "视频已保存，可以随时下载"
            : null);

  return (
    <div className="flex items-center gap-3">
      {videoUrl ? (
        <button
          type="button"
          onClick={() => void download(videoUrl, "mp4", "video")}
          disabled={downloading !== null}
          className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <span aria-hidden="true">↓</span>
          {downloading === "video" ? "准备下载…" : "下载 MP4"}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={submitting || exporting}
          aria-busy={submitting || exporting}
          className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <span aria-hidden="true">▶</span>
          {submitting
            ? "提交中…"
            : exporting
              ? `导出视频 ${job?.progress ?? 0}%`
              : "导出 MP4"}
        </button>
      )}
      {subtitleUrl ? (
        <button
          type="button"
          onClick={() => void download(subtitleUrl, "srt", "subtitle")}
          disabled={downloading !== null}
          className="rounded-full border border-(--shell-border) bg-white px-3 py-2 text-xs font-bold text-(--accent-strong)"
        >
          {downloading === "subtitle" ? "准备中…" : "下载 SRT"}
        </button>
      ) : null}
      <span
        role="status"
        aria-live="polite"
        className="max-w-64 text-xs text-(--muted-text)"
      >
        {status}
      </span>
    </div>
  );
}
