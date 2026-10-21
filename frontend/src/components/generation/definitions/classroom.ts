import type { GenerationConfigDefinition } from "./types";

export type ClassroomConfig = {
  topic: string;
  audience: string;
  objectives: string[];
  durationMinutes?: number;
  teachingStyle?: "guided" | "lecture" | "inquiry";
  voiceEnabled?: boolean;
  voice: string;
  specialRequirements: string;
  includeVisuals?: boolean;
};

export const classroomDefinition: GenerationConfigDefinition<ClassroomConfig> = {
  resourceType: "classroom",
  title: "配置 AI 课堂",
  description: "填写主题和需求，生成教学视频。",
  defaultConfig: () => ({ topic: "", audience: "", objectives: [], voice: "", specialRequirements: "" }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入课堂主题" }),
  }),
  serialize: ({ config }) => ({
    topic: config.topic.trim(),
    audience: config.audience.trim(),
    objectives: config.objectives.map((item) => item.trim()).filter(Boolean),
    duration_minutes: config.durationMinutes,
    teaching_style: config.teachingStyle,
    enable_tts: config.voiceEnabled,
    voice: config.voice || undefined,
    enable_web_search: false,
    include_visuals: config.includeVisuals,
    requirement: [config.topic.trim(), config.objectives.length ? `教学目标：${config.objectives.join("；")}` : "", config.teachingStyle ? `教学方式：${config.teachingStyle}` : "", config.specialRequirements.trim()].filter(Boolean).join("\n"),
  }),
};
