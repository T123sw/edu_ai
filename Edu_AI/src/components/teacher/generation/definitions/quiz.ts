import type { GenerationConfigDefinition } from "./types";

export type QuizQuestionType = "choice" | "blank" | "short" | "judge";
export type QuizConfig = {
  topic: string;
  audience: string;
  difficulty: "easy" | "medium" | "hard";
  count: number;
  questionTypes: QuizQuestionType[];
  includeAnswers: boolean;
  includeExplanations: boolean;
};

export const quizDefinition: GenerationConfigDefinition<QuizConfig> = {
  resourceType: "quiz",
  title: "配置习题",
  description: "题量、题型、答案和解析分别控制，资料为空时仍可按主题生成。",
  defaultConfig: () => ({ topic: "", audience: "本科一年级", difficulty: "medium", count: 10, questionTypes: ["choice"], includeAnswers: true, includeExplanations: true }),
  validate: (config) => ({
    ...(config.topic.trim() ? {} : { topic: "请输入习题主题" }),
    ...(config.count >= 1 && config.count <= 50 ? {} : { count: "题目数量需为 1–50" }),
    ...(config.questionTypes.length ? {} : { questionTypes: "至少选择一种题型" }),
  }),
  serialize: ({ config }) => ({ quiz_config: { topic: config.topic.trim(), audience: config.audience.trim(), difficulty: config.difficulty, question_count: config.count, question_types: [...config.questionTypes], include_answers: config.includeAnswers, include_explanations: config.includeExplanations, hard_points: [] } }),
};
