export type GenerationResourceType =
  | "report" | "lesson_plan" | "blog" | "quiz"
  | "flashcard" | "mind_map" | "game" | "classroom";

export type GenerationRegistryItem = {
  resourceType: GenerationResourceType;
  label: string;
  description: string;
  icon: string;
  accent: string;
  definition: object;
};

export const generationRegistry: readonly GenerationRegistryItem[] = [
  { resourceType: "report", label: "教学报告", description: "整理课程主题、资料与教学建议", icon: "article", accent: "#b7791f", definition: reportDefinition },
  { resourceType: "lesson_plan", label: "教案", description: "生成可编辑的教学目标和教学过程", icon: "menu_book", accent: "#5b6fd8", definition: lessonPlanDefinition },
  { resourceType: "blog", label: "教学博客", description: "生成适合分享和延伸阅读的长文", icon: "description", accent: "#d65f59", definition: blogDefinition },
  { resourceType: "quiz", label: "习题", description: "生成题目、答案与可选解析", icon: "quiz", accent: "#3157d5", definition: quizDefinition },
  { resourceType: "flashcard", label: "闪卡", description: "生成便于复习和课堂抽查的卡片", icon: "fact_check", accent: "#8b4bc2", definition: flashcardDefinition },
  { resourceType: "mind_map", label: "思维导图", description: "梳理主题层级与概念关系", icon: "account_tree", accent: "#c0448a", definition: mindMapDefinition },
  { resourceType: "game", label: "课堂小游戏", description: "生成分类、配对或记忆互动", icon: "play_circle", accent: "#26765b", definition: gameDefinition },
  { resourceType: "classroom", label: "AI 课堂", description: "生成包含讲解和互动场景的课堂", icon: "school", accent: "#126e82", definition: classroomDefinition },
] as const;

export function getGenerationResource(type: GenerationResourceType) {
  return generationRegistry.find((item) => item.resourceType === type) ?? generationRegistry[0];
}

export function selectGenerationResources(allowedTools: readonly GenerationResourceType[]) {
  const definitions = new Map(generationRegistry.map((item) => [item.resourceType, item]));
  const selected: GenerationRegistryItem[] = [];
  const seen = new Set<GenerationResourceType>();
  for (const toolId of allowedTools) {
    const item = definitions.get(toolId);
    if (!item || seen.has(toolId)) continue;
    seen.add(toolId);
    selected.push(item);
  }
  return selected;
}
import { reportDefinition } from "./definitions/report";
import { lessonPlanDefinition } from "./definitions/lessonPlan";
import { blogDefinition } from "./definitions/blog";
import { quizDefinition } from "./definitions/quiz";
import { flashcardDefinition } from "./definitions/flashcard";
import { mindMapDefinition } from "./definitions/mindMap";
import { gameDefinition } from "./definitions/game";
import { classroomDefinition } from "./definitions/classroom";
