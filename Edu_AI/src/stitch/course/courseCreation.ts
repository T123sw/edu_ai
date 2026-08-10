import type { BackendCourseCreatePayload } from "../api/types";

export const COURSE_LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "中文" },
  { value: "en", label: "English" },
  { value: "bilingual", label: "中英双语" },
] as const;

export const COURSE_DIFFICULTY_OPTIONS = [
  { value: "introductory", label: "入门" },
  { value: "intermediate", label: "进阶" },
  { value: "advanced", label: "高阶" },
] as const;

export type CourseCreationDraft = {
  title: string;
  description: string;
  audience: string;
  objectivesText: string;
  language: string;
  difficulty: string;
};

export type CourseCreationErrors = Partial<Record<keyof CourseCreationDraft, string>>;

export const EMPTY_COURSE_CREATION_DRAFT: CourseCreationDraft = {
  title: "",
  description: "",
  audience: "",
  objectivesText: "",
  language: "zh-CN",
  difficulty: "introductory",
};

export function buildCourseCreatePayload(
  draft: CourseCreationDraft,
): { payload: BackendCourseCreatePayload | null; errors: CourseCreationErrors } {
  const title = draft.title.trim();
  const description = draft.description.trim();
  const audience = draft.audience.trim();
  const objectives = draft.objectivesText
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  const errors: CourseCreationErrors = {};

  if (!title) errors.title = "请输入课程名称";
  if (!description) errors.description = "请填写课程简介";
  if (!audience) errors.audience = "请填写教学对象或年级";
  if (!objectives.length) errors.objectivesText = "请至少填写一个课程目标";
  if (!draft.language) errors.language = "请选择授课语言";
  if (!draft.difficulty) errors.difficulty = "请选择课程难度";

  if (Object.keys(errors).length) return { payload: null, errors };

  return {
    payload: {
      title,
      description,
      audience,
      objectives,
      language: draft.language,
      difficulty: draft.difficulty,
      icon: "menu_book",
      color: "#3157d5",
      knowledgeGraph: "",
    },
    errors,
  };
}
