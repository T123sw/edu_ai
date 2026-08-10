import type { LearningTask, TaskProgress } from "../api/types";

export type LearningActor = "teacher" | "student";
export type LearningTaskPrimaryAction =
  | "publish"
  | "start"
  | "continue"
  | "completed"
  | "none";

type LearningTaskState = Pick<LearningTask, "status"> & {
  my_progress: Pick<TaskProgress, "status" | "progress_percent"> | null;
};

export function getLearningTaskPrimaryAction(
  actor: LearningActor,
  task: LearningTaskState,
): LearningTaskPrimaryAction {
  if (actor === "teacher") {
    return task.status === "draft" ? "publish" : "none";
  }
  if (task.status !== "published") return "none";
  if (!task.my_progress || task.my_progress.status === "not_started") return "start";
  if (task.my_progress.status === "completed") return "completed";
  return "continue";
}

export function getProgressLabel(progressPercent: number): string {
  const normalized = Math.min(100, Math.max(0, Math.round(Number(progressPercent) || 0)));
  if (normalized === 0) return "未开始";
  if (normalized === 100) return "已完成";
  return `已完成 ${normalized}%`;
}
