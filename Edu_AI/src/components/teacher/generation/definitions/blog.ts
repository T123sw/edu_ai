import type { GenerationConfigDefinition } from "./types";

export type BlogConfig = {
  topic: string;
  audience: string;
  tone: "academic" | "popular" | "narrative";
  length: "short" | "medium" | "long";
  structure: string;
  specialRequirements: string;
};

export const blogDefinition: GenerationConfigDefinition<BlogConfig> = {
  resourceType: "blog",
  title: "配置教学博客",
  description: "明确读者、语气和文章结构，生成适合分享的课程长文。",
  defaultConfig: () => ({
    topic: "",
    audience: "本科生",
    tone: "popular",
    length: "medium",
    structure: "概念引入—核心解释—案例—总结",
    specialRequirements: "",
  }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入博客主题" }),
    ...(config.audience.trim() ? {} : { audience: "请输入目标读者" }),
  }),
  serialize: ({ config }) => ({
    topic: config.topic.trim(),
    audience: config.audience.trim(),
    tone: config.tone,
    length: config.length,
    structure: config.structure.trim(),
    special_requirements: config.specialRequirements.trim(),
  }),
};
