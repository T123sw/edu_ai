import type { JobRecord } from "./types";

const JOB_KIND_LABELS: Record<string, string> = {
  generate_classroom: "AI 课堂生成",
  render_video: "课堂视频导出",
  generate_report: "报告生成",
  generate_lesson_plan: "教案生成",
  generate_blog: "教学博客生成",
  generate_quiz: "习题生成",
  generate_ppt: "PPT 生成",
  generate_flashcard: "闪卡生成",
  generate_graph: "思维导图生成",
  generate_game: "小游戏生成",
  ingest_video: "视频入库",
  rag_import: "知识库索引",
  parse_document: "文档解析",
  build_knowledge_index: "知识库索引",
};

export function jobKindLabel(kind: string): string {
  return JOB_KIND_LABELS[kind] ?? "后台任务";
}

export type JobQualitySummary = {
  completedCount: number;
  failureCount: number;
  failureRate: number;
  averageDurationMs: number;
};

export function summarizeJobs(jobs: JobRecord[]): JobQualitySummary {
  const completed = jobs.filter(
    (job) =>
      job.status === "succeeded" ||
      job.status === "partially_succeeded" ||
      job.status === "failed",
  );
  const failureCount = completed.filter(
    (job) =>
      job.status === "failed" || job.status === "partially_succeeded",
  ).length;
  const durations = completed
    .map((job) => {
      if (!job.started_at || !job.finished_at) return 0;
      const startedAt = Date.parse(job.started_at);
      const finishedAt = Date.parse(job.finished_at);
      return Number.isFinite(startedAt) && Number.isFinite(finishedAt)
        ? Math.max(0, finishedAt - startedAt)
        : 0;
    })
    .filter((duration) => duration > 0);

  return {
    completedCount: completed.length,
    failureCount,
    failureRate: completed.length
      ? Math.round((failureCount / completed.length) * 100)
      : 0,
    averageDurationMs: durations.length
      ? Math.round(
          durations.reduce((total, duration) => total + duration, 0) /
            durations.length,
        )
      : 0,
  };
}
