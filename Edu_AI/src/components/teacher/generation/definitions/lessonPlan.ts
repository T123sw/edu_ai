import type { GenerationConfigDefinition } from "./types";

export type LessonPlanConfig = {
  topic: string;
  audience: string;
  durationMinutes: number;
  objectives: string[];
  lessonType: "new_lesson" | "review_lesson" | "inquiry_lesson" | "practice_lesson";
  teachingProcess: string;
  specialRequirements: string;
  outlinePreview: boolean;
};

export const lessonPlanDefinition: GenerationConfigDefinition<LessonPlanConfig> = {
  resourceType: "lesson_plan",
  title: "配置教案",
  description: "按基本信息、教学目标、教学过程和补充要求组织，所有建议都可编辑。",
  defaultConfig: () => ({
    topic: "",
    audience: "本科一年级",
    durationMinutes: 45,
    objectives: ["理解核心概念并能用于典型问题"],
    lessonType: "new_lesson",
    teachingProcess: "情境导入—概念讲解—练习反馈—课堂总结",
    specialRequirements: "",
    outlinePreview: true,
  }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入教学主题" }),
    ...(config.audience.trim() ? {} : { audience: "请输入年级或适用对象" }),
    ...(config.durationMinutes >= 10 && config.durationMinutes <= 480 ? {} : { durationMinutes: "课时需为 10–480 分钟" }),
    ...(config.objectives.some((item) => item.trim()) ? {} : { objectives: "至少填写一个教学目标" }),
  }),
  serialize: ({ config }) => ({
    topic: config.topic.trim(),
    audience: config.audience.trim(),
    duration_minutes: config.durationMinutes,
    objectives: config.objectives.map((item) => item.trim()).filter(Boolean),
    lesson_type: config.lessonType,
    teaching_process: config.teachingProcess.trim(),
    special_requirements: config.specialRequirements.trim(),
    outline_preview: config.outlinePreview,
  }),
};
