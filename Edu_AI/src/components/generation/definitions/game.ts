import type { GenerationConfigDefinition } from "./types";

export type GameConfig = { gameType: "category_sort" | "drag_match" | "memory_flip"; topic: string; cardCount: number; difficulty: "easy" | "medium" | "hard"; durationMinutes: number };

export const gameDefinition: GenerationConfigDefinition<GameConfig> = {
  resourceType: "game",
  title: "配置课堂小游戏",
  description: "选择一种可操作的互动模板，并控制题量、难度和课堂用时。",
  defaultConfig: () => ({ gameType: "category_sort", topic: "", cardCount: 8, difficulty: "medium", durationMinutes: 5 }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入游戏主题" }),
    ...(config.cardCount >= 4 && config.cardCount <= 30 ? {} : { cardCount: "卡片数量需为 4–30" }),
    ...(config.durationMinutes >= 1 && config.durationMinutes <= 60 ? {} : { durationMinutes: "课堂用时需为 1–60 分钟" }),
  }),
  serialize: ({ config }) => ({ game_type: config.gameType, topic: config.topic.trim(), card_count: config.cardCount, difficulty: config.difficulty, duration_minutes: config.durationMinutes }),
};
