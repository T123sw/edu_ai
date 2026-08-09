import type { GenerationConfigDefinition } from "./types";

export type ClassroomConfig = {
  topic: string;
  audience: string;
  objectives: string[];
  sceneCount: number;
  durationMinutes: number;
  teachingStyle: "guided" | "lecture" | "inquiry";
  voiceEnabled: boolean;
  voice: "alloy" | "nova" | "shimmer";
  specialRequirements: string;
  includeVisuals: boolean;
};

export const classroomDefinition: GenerationConfigDefinition<ClassroomConfig> = {
  resourceType: "classroom",
  title: "配置 AI 课堂",
  description: "输入研究主题，系统自动组织课堂结构并生成可播放内容。",
  defaultConfig: () => ({ topic: "", audience: "本科一年级", objectives: ["理解核心概念"], sceneCount: 6, durationMinutes: 25, teachingStyle: "guided", voiceEnabled: true, voice: "alloy", specialRequirements: "", includeVisuals: true }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入课堂主题" }),
  }),
  serialize: ({ config }) => ({
    topic: config.topic.trim(),
    audience: config.audience.trim(),
    objectives: config.objectives.map((item) => item.trim()).filter(Boolean),
    scene_count: config.sceneCount,
    duration_minutes: config.durationMinutes,
    teaching_style: config.teachingStyle,
    enable_tts: config.voiceEnabled,
    voice: config.voiceEnabled ? config.voice : "",
    enable_web_search: false,
    include_visuals: config.includeVisuals !== false,
    requirement: [config.topic.trim(), `教学目标：${config.objectives.join("；")}`, `教学方式：${config.teachingStyle}`, config.specialRequirements.trim()].filter(Boolean).join("\n"),
  }),
};
