import type { LearningOverview } from "../api/types";

export type CourseLearningMetric = {
  label: string;
  value: number | string;
};

export function toCourseLearningMetrics(
  actor: "teacher" | "student",
  overview: LearningOverview | null,
  activeJobCount: number,
): CourseLearningMetric[] {
  return [
    {
      label: actor === "student" ? "待学习任务" : "进行中学习任务",
      value: overview
        ? actor === "student"
          ? overview.pending_tasks
          : overview.in_progress_tasks
        : "—",
    },
    { label: "后台生成中", value: activeJobCount },
  ];
}
