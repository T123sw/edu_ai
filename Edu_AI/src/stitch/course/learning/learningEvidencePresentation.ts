import type { CompletionBasis, LearningTask } from "../../api/types";

const BASIS_RANK: Record<CompletionBasis, number> = {
  none: 0,
  self_reported: 1,
  activity_evidenced: 2,
  assessment_verified: 3,
};

export function strongerCompletionBasis(
  current: CompletionBasis,
  incoming: CompletionBasis,
): CompletionBasis {
  return BASIS_RANK[incoming] > BASIS_RANK[current] ? incoming : current;
}

export function taskNeedsAssessment(
  task: Pick<LearningTask, "task_type">,
): boolean {
  return task.task_type === "assessed";
}

export function taskTypeLabel(taskType: LearningTask["task_type"]): string {
  return taskType === "reading" ? "阅读学习" : "考核任务";
}
