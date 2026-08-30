import type { CourseKnowledgeBuildConfig } from "../../api/types";

export const COURSE_KNOWLEDGE_PRESETS = {
  small: { graph_depth: 3, target_module_count: 3, target_points_per_module: 3, target_materials_per_leaf: 3 },
  standard: { graph_depth: 3, target_module_count: 4, target_points_per_module: 4, target_materials_per_leaf: 3 },
  large: { graph_depth: 3, target_module_count: 6, target_points_per_module: 6, target_materials_per_leaf: 3 },
} as const;

export const DEFAULT_COURSE_KNOWLEDGE_CONFIG: CourseKnowledgeBuildConfig = {
  preset: "standard",
  graph_depth: 3,
  target_module_count: 4,
  target_points_per_module: 4,
  target_materials_per_leaf: 3,
  minimum_web_materials_per_leaf: 1,
  maximum_ai_materials_per_leaf: 1,
  max_search_results_per_leaf: 8,
  prefer_complete_textbooks: true,
  max_online_textbooks: 2,
  max_search_rounds_per_leaf: 2,
  ai_supplement_enabled: true,
  content_language: "zh-CN",
  update_strategy: "merge_rebuild",
};

export function applyCourseKnowledgePreset(
  config: CourseKnowledgeBuildConfig,
  preset: "small" | "standard" | "large",
): CourseKnowledgeBuildConfig {
  return { ...config, ...COURSE_KNOWLEDGE_PRESETS[preset], preset };
}

export function estimateCourseKnowledgeBuild(config: CourseKnowledgeBuildConfig) {
  const leafCount = config.target_module_count * config.target_points_per_module;
  return {
    leafCount,
    materialCount: leafCount * config.target_materials_per_leaf,
  };
}

export function validateCourseKnowledgeConfig(config: CourseKnowledgeBuildConfig): string[] {
  const errors: string[] = [];
  const range = (value: number, min: number, max: number, label: string) => {
    if (!Number.isInteger(value) || value < min || value > max) {
      errors.push(`${label}必须是 ${min}～${max} 的整数`);
    }
  };
  range(config.graph_depth, 3, 5, "图谱深度");
  range(config.target_module_count, 1, 12, "模块数量");
  range(config.target_points_per_module, 2, 20, "每模块知识点");
  range(config.target_materials_per_leaf, 1, 10, "每知识点资料数");
  range(config.minimum_web_materials_per_leaf, 0, 10, "外部非 AI 来源下限");
  range(config.maximum_ai_materials_per_leaf, 0, 10, "AI 补充上限");
  range(config.max_search_results_per_leaf, 1, 20, "搜索候选上限");
  range(config.max_online_textbooks, 0, 5, "在线教材上限");
  range(config.max_search_rounds_per_leaf, 1, 3, "搜索轮次");
  if (config.minimum_web_materials_per_leaf > config.target_materials_per_leaf) {
    errors.push("外部非 AI 来源下限不能大于每知识点资料目标");
  }
  if (config.maximum_ai_materials_per_leaf > config.target_materials_per_leaf) {
    errors.push("AI 补充上限不能大于每知识点资料目标");
  }
  return errors;
}
