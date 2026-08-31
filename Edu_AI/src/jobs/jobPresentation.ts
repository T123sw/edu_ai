import { isActiveJob, type JobRecord } from "./types";

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

export type JobUserMessage = {
  title: string;
  detail: string;
};

const JOB_ERROR_MESSAGES: Record<string, JobUserMessage> = {
  SOURCE_SELECTION_REQUIRED: {
    title: "没有可用的参考资料",
    detail: "请选择课程知识或个人资料后再试。",
  },
  GENERATION_DEADLINE_EXCEEDED: {
    title: "生成时间过长",
    detail: "任务已安全停止，请稍后重试。",
  },
  WORKER_LOST: {
    title: "后台执行中断",
    detail: "任务未能自动恢复，请重新提交。",
  },
  MAX_ATTEMPTS_EXCEEDED: {
    title: "多次尝试仍未完成",
    detail: "请稍后重试；如持续发生，请联系管理员。",
  },
  PROVIDER_UNAVAILABLE: {
    title: "生成服务暂时不可用",
    detail: "系统会自动重试，也可以稍后再次提交。",
  },
  UNSUPPORTED_HANDLER_VERSION: {
    title: "任务版本已过期",
    detail: "请重新发起一次生成任务。",
  },
  TASK_EXECUTION_FAILED: {
    title: "生成过程未完成",
    detail: "请检查输入后重试。",
  },
  RESOURCE_READBACK_FAILED: {
    title: "结果暂时无法打开",
    detail: "内容可能已经生成，请刷新课程资源后再试。",
  },
  RESOURCE_PROVENANCE_MISMATCH: {
    title: "结果校验未通过",
    detail: "系统未展示不确定的结果，请重新生成。",
  },
  LEGACY_TASK_NOT_RECOVERABLE: {
    title: "旧任务无法继续",
    detail: "请重新发起一次生成任务。",
  },
  GENERATION_CANCELLED: {
    title: "任务已取消",
    detail: "本次生成已停止。",
  },
};

export function presentJobError(job: JobRecord): JobUserMessage {
  const errorCode = String(job.error_code || "").trim();
  const known = JOB_ERROR_MESSAGES[errorCode];
  if (known) return known;
  if (job.status === "partially_succeeded") {
    return {
      title: "任务只完成了一部分",
      detail: "可先打开已有结果，或重新生成缺失内容。",
    };
  }
  return {
    title: "任务暂时未完成",
    detail: `请稍后重试；如持续发生，请提供任务 ID：${job.edu_job_id}`,
  };
}

/**
 * Keep the task center user-facing even when an older worker stored an English
 * implementation message in `job.message` or `job.step`.
 */
export function presentJobDetail(job: JobRecord): string {
  if (job.status === "failed" || job.status === "partially_succeeded") {
    const error = presentJobError(job);
    return `${error.title}：${error.detail}`;
  }

  if (job.status === "succeeded") {
    return job.kind === "render_video"
      ? "导出完成，可以打开结果。"
      : "生成完成，结果已保存到课程资源。";
  }

  if (job.status === "canceled") return "任务已取消。";
  if (job.status === "cancel_requested") return "正在安全停止任务…";
  if (job.status === "queued") return "任务已提交，正在等待后台处理。";
  if (job.status === "running") return "后台正在处理中，请稍候。";
  return "任务状态已更新。";
}

export type JobStatusSummary = {
  completedCount: number;
  activeCount: number;
  failedCount: number;
};

export function summarizeJobs(jobs: JobRecord[]): JobStatusSummary {
  return {
    completedCount: jobs.filter((job) => job.status === "succeeded").length,
    activeCount: jobs.filter(isActiveJob).length,
    failedCount: jobs.filter(
      (job) =>
        job.status === "failed" || job.status === "partially_succeeded",
    ).length,
  };
}

export type JobPrimaryAction = "cancel" | "retry" | "open-result";

export function isJobCenterVisible(job: JobRecord): boolean {
  return job.status !== "canceled";
}

export function getJobPrimaryAction(
  job: JobRecord,
  resultHash?: string | null,
): JobPrimaryAction | null {
  if (isActiveJob(job) && job.cancelable) return "cancel";
  if (
    (job.status === "failed" || job.status === "partially_succeeded") &&
    job.retryable
  ) {
    return "retry";
  }
  if (job.status === "succeeded" && resultHash) return "open-result";
  return null;
}
