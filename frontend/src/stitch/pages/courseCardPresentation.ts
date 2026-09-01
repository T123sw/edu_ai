import type { BackendCourse, LearningOverview } from "../api/types";
import { toCourseLearningMetrics } from "./courseLearningOverview";

export type CourseCardFacts = {
  documentCount: number;
  resourceCount: number;
  activeJobCount: number;
  learningOverview: LearningOverview | null;
};

export function toCourseCardPresentation(
  course: Pick<BackendCourse, "id" | "title" | "description" | "updated_at">,
  facts: CourseCardFacts,
  actor: "teacher" | "student" = "teacher",
) {
  const updated = course.updated_at ? new Date(course.updated_at) : null;
  const updatedText = updated && !Number.isNaN(updated.getTime())
    ? `${updated.getMonth() + 1}月${updated.getDate()}日 ${updated.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}`
    : null;

  return {
    id: course.id,
    title: course.title,
    description: course.description || "暂未填写课程简介",
    updatedLabel: updatedText ? `最近更新 ${updatedText}` : "暂无更新记录",
    metrics: [
      ...toCourseLearningMetrics(actor, facts.learningOverview, facts.activeJobCount),
      { label: "课程资料", value: facts.documentCount },
      { label: "个人资源", value: facts.resourceCount },
    ],
    learningStatusLabel: facts.learningOverview ? null : "学习任务暂不可用",
  };
}
