import type { CompletionBasis, LearningTask, TaskProgress, TaskResourceEvidence } from "../api/types";

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

export function getProgressLabel(
  progressPercent: number,
  status: TaskProgress["status"],
): string {
  const value = Math.min(100, Math.max(0, Math.round(Number(progressPercent) || 0)));
  if (status === "not_started") return "未开始";
  if (status === "completed" || value === 100) return "已完成";
  return `进行中 · ${value}%`;
}

export function getCompletionBasisLabel(
  basis: CompletionBasis | null | undefined,
  status: TaskProgress["status"] = "not_started",
): string {
  const resolvedBasis = basis ?? (status === "completed" ? "self_reported" : "none");
  return {
    none: "暂无完成证据",
    self_reported: "学生自报完成",
    activity_evidenced: "已有活动证据",
    assessment_verified: "测评已验证",
  }[resolvedBasis];
}

export function getTaskResourceEvidenceLabel(
  evidence: Pick<TaskResourceEvidence, "condition_status" | "resource_version">,
): string {
  const status = evidence.condition_status === "satisfied"
    ? "资源条件已满足"
    : "资源条件待完成";
  return `${status} · 证据版本 ${evidence.resource_version}`;
}
