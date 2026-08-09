import type { GenerationConfigDefinition } from "./types";

export type MindMapConfig = { topic: string; description: string; depth: number };

export const mindMapDefinition: GenerationConfigDefinition<MindMapConfig> = {
  resourceType: "mind_map",
  title: "配置思维导图",
  description: "生成独立的思维导图资源，不会改写课程知识结构。",
  defaultConfig: () => ({ topic: "", description: "突出概念层级、因果和对比关系", depth: 3 }),
  validate: (config) => ({ ...(config.topic.trim() ? {} : { topic: "请输入思维导图主题" }), ...(config.depth >= 2 && config.depth <= 5 ? {} : { depth: "层级深度需为 2–5" }) }),
  serialize: ({ config }) => ({ title: config.topic.trim(), description: config.description.trim(), max_depth: config.depth }),
};
