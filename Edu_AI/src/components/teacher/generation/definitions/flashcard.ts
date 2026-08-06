import type { GenerationConfigDefinition } from "./types";

export type FlashcardConfig = { title: string; count: number; difficulty: "easy" | "medium" | "hard"; category: string; showSource: boolean };

export const flashcardDefinition: GenerationConfigDefinition<FlashcardConfig> = {
  resourceType: "flashcard",
  title: "配置闪卡",
  description: "为课堂抽查或复习设置卡片标题、数量和难度。标题始终按纯文本处理。",
  defaultConfig: () => ({ title: "", count: 12, difficulty: "medium", category: "核心概念", showSource: true }),
  validate: (config) => ({
    ...(config.title.trim() ? {} : { title: "请输入闪卡标题" }),
    ...(config.count >= 3 && config.count <= 30 ? {} : { count: "卡片数量需为 3–30" }),
  }),
  serialize: ({ config }) => ({ flashcard_config: { title: config.title.trim(), count: config.count, difficulty: config.difficulty, category: config.category.trim(), show_sources: config.showSource } }),
};
