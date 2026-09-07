import type { BackendCourse, LearningOverview } from "../api/types";
import { toCourseLearningMetrics } from "./courseLearningOverview";

export type CourseCardFacts = {
  documentCount: number;
  resourceCount: number;
  activeJobCount: number;
  learningOverview: LearningOverview | null;
};

export function toCourseCardPresentation(
  course: Pick<BackendCourse, "id" | "title" | "description" | "updated_at" | "last_used_at">,
  facts: CourseCardFacts,
  actor: "teacher" | "student" = "teacher",
  previousVisit?: { courseId: string; visitedAt: string } | null,
) {
  const times = [course.last_used_at, previousVisit?.courseId === course.id ? previousVisit.visitedAt : null]
    .filter((value): value is string => Boolean(value))
    .map(Date.parse).filter(Number.isFinite);
  const used = times.length ? new Date(Math.max(...times)) : null;
  const usedText = used
    ? used.toLocaleString("zh-CN", { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })
    : null;

  return {
    id: course.id,
    title: course.title,
    description: course.description || "暂未填写课程简介",
    updatedLabel: usedText ? `最近使用 ${usedText}` : "暂无使用记录",
    metrics: [
      ...toCourseLearningMetrics(actor, facts.learningOverview, facts.activeJobCount),
      { label: "课程资料", value: facts.documentCount },
      { label: "个人资源", value: facts.resourceCount },
    ],
    learningStatusLabel: facts.learningOverview ? null : "学习任务暂不可用",
  };
}
