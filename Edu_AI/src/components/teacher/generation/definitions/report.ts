import type { GenerationConfigDefinition } from "./types";

export type ReportConfig = {
  template: "brief" | "detailed" | "study_plan" | "custom";
  topic: string;
  audience: string;
  depth: "overview" | "standard" | "deep";
  structureEmphasis: string;
  specialRequirements: string;
  includeVisuals: boolean;
};

export const reportDefinition: GenerationConfigDefinition<ReportConfig> = {
  resourceType: "report",
  title: "配置教学报告",
  description: "确定报告用途、分析深度和结构重点。固定模板可立即使用。",
  defaultConfig: () => ({
    template: "detailed",
    topic: "",
    audience: "教研组",
    depth: "standard",
    structureEmphasis: "结论、依据与可执行建议",
    specialRequirements: "",
    includeVisuals: true,
  }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入报告主题" }),
  }),
  serialize: ({ config }) => ({
    question: config.topic.trim(),
    report_config: {
      template: config.template,
      audience: config.audience.trim(),
      depth: config.depth,
      structure_emphasis: config.structureEmphasis.trim(),
      special_requirements: config.specialRequirements.trim(),
      include_visuals: config.includeVisuals !== false,
    },
  }),
};
