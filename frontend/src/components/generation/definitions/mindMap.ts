import type { GenerationConfigDefinition } from "./types";

export type MindMapConfig = { topic: string; description: string; depth: number };

// These instructions travel with the request to the model, including on servers
// running the previous generator. Generated text is never shortened in code.
export const mindMapWritingGuidance = "导图用于快速看清知识结构。节点标题使用简短、明确的概念名；summary 由你按语义直接概括为一个短语或短句，只说明该节点最核心的作用、区别或关系。不要重复标题，不铺陈背景，不罗列多个知识点，不放长例子、代码或完整推导。标题已能表达含义时，summary 可以留空。父节点说明不要重复子节点内容；必要的知识点放在合适的子节点中。请自行提炼并写出完整意思，不要截取原文首句或用省略号代替概括。例如“划分”的说明可写“把小于基准的元素移到左侧”。";

export const mindMapDefinition: GenerationConfigDefinition<MindMapConfig> = {
  resourceType: "mind_map",
  title: "配置思维导图",
  description: "生成独立的思维导图资源，不会改写课程知识结构。",
  defaultConfig: () => ({ topic: "", description: "突出概念层级、因果和对比关系", depth: 3 }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入思维导图主题" }),
    ...(config.depth >= 2 && config.depth <= 5 ? {} : { depth: "层级深度需为 2–5" }),
    ...([...config.description.trim(), ...mindMapWritingGuidance].length + 2 <= 2000 ? {} : { description: "关系侧重点过长，请精简后再生成" }),
  }),
  serialize: ({ config }) => ({ title: config.topic.trim(), description: [config.description.trim(), mindMapWritingGuidance].filter(Boolean).join("\n\n"), max_depth: config.depth }),
};
