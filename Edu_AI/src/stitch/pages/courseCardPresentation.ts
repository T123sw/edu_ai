import type { BackendCourse } from "../api/types";

export type CourseCardFacts = {
  documentCount: number;
  resourceCount: number;
  activeJobCount: number;
};

const roleLabels = {
  owner: "课程负责人",
  editor: "课程编辑者",
  viewer: "课程查看者",
} as const;

export function toCourseCardPresentation(
  course: Pick<BackendCourse, "id" | "title" | "description" | "membership_role" | "revision" | "updated_at">,
  facts: CourseCardFacts,
) {
  const updated = course.updated_at ? new Date(course.updated_at) : null;
  const updatedText = updated && !Number.isNaN(updated.getTime())
    ? updated.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "暂无更新时间";

  return {
    id: course.id,
    title: course.title,
    description: course.description || "暂未填写课程简介",
    roleLabel: roleLabels[course.membership_role],
    revisionLabel: `版本 ${course.revision}`,
    updatedLabel: `更新于 ${updatedText}`,
    metrics: [
      { label: "课程资料", value: facts.documentCount },
      { label: "课程资源", value: facts.resourceCount },
      { label: "进行中任务", value: facts.activeJobCount },
    ],
  };
}
