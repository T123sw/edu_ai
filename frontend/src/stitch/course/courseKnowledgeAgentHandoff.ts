import type { BackendCourse } from "../api/types";


export function buildNewCourseKnowledgeAgentPrompt(
  course: BackendCourse,
  knowledgeRequirements = "",
): string {
  const details = [
    `课程名称：${course.title.trim()}`,
    course.description.trim() ? `课程简介：${course.description.trim()}` : null,
    course.audience?.trim() ? `教学对象：${course.audience.trim()}` : null,
    course.difficulty?.trim() ? `课程难度：${course.difficulty.trim()}` : null,
    course.language?.trim() ? `内容语言：${course.language.trim()}` : null,
    course.objectives?.length
      ? `课程目标：${course.objectives.map((item) => item.trim()).filter(Boolean).join("；")}`
      : null,
    knowledgeRequirements.trim()
      ? `知识库构建要求：${knowledgeRequirements.trim()}`
      : null,
  ].filter((item): item is string => Boolean(item));

  return [
    "请根据刚创建课程的权威信息，为这门课规划课程知识库。先生成可审核方案，不要直接发布。",
    ...details,
  ].join("\n");
}
