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
};

export const classroomDefinition: GenerationConfigDefinition<ClassroomConfig> = {
  resourceType: "classroom",
  title: "配置 AI 课堂",
  description: "设置课堂目标、场景节奏、教学方式和配音；生成后可直接播放。",
  defaultConfig: () => ({ topic: "", audience: "本科一年级", objectives: ["理解核心概念"], sceneCount: 6, durationMinutes: 25, teachingStyle: "guided", voiceEnabled: true, voice: "alloy", specialRequirements: "" }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入课堂主题" }),
    ...(config.objectives.some((item) => item.trim()) ? {} : { objectives: "至少填写一个课堂目标" }),
    ...(config.sceneCount >= 1 && config.sceneCount <= 30 ? {} : { sceneCount: "场景数量需为 1–30" }),
    ...(config.durationMinutes >= 5 && config.durationMinutes <= 180 ? {} : { durationMinutes: "课堂时长需为 5–180 分钟" }),
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
    requirement: [config.topic.trim(), `教学目标：${config.objectives.join("；")}`, `教学方式：${config.teachingStyle}`, config.specialRequirements.trim()].filter(Boolean).join("\n"),
  }),
};
