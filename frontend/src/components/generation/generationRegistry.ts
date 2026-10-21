export type GenerationResourceType =
  | "report" | "lesson_plan" | "blog" | "quiz"
  | "flashcard" | "mind_map" | "game" | "classroom";

export type CanonicalGenerationResourceType = Exclude<GenerationResourceType, "mind_map"> | "graph";

export type GenerationRegistryItem = {
  resourceType: GenerationResourceType;
  label: string;
  description: string;
  icon: string;
  accent: string;
  canonicalType: CanonicalGenerationResourceType;
  actionHint: `generate.${CanonicalGenerationResourceType}`;
  placeholder: string;
  definition: object;
};

export const generationRegistry: readonly GenerationRegistryItem[] = [
  { resourceType: "report", canonicalType: "report", actionHint: "generate.report", label: "教学报告", description: "整理课程主题、资料与教学建议", placeholder: "例如：生成一份面向大一学生的数组随机访问教学报告，语言通俗，包含原理、示例和常见误区，约 1500 字。", icon: "article", accent: "#b7791f", definition: reportDefinition },
  { resourceType: "lesson_plan", canonicalType: "lesson_plan", actionHint: "generate.lesson_plan", label: "教案", description: "生成可编辑的教学目标和教学过程", placeholder: "例如：为高中一年级设计一节 40 分钟的函数单调性教案，安排小组探究和形成性评价，先给我教学方案。", icon: "menu_book", accent: "#5b6fd8", definition: lessonPlanDefinition },
  { resourceType: "blog", canonicalType: "blog", actionHint: "generate.blog", label: "教学博客", description: "生成适合分享和延伸阅读的长文", placeholder: "例如：写一篇面向零基础读者的递归入门博客，用生活类比和两个代码示例，语气轻松。", icon: "description", accent: "#d65f59", definition: blogDefinition },
  { resourceType: "quiz", canonicalType: "quiz", actionHint: "generate.quiz", label: "习题", description: "生成题目、答案与可选解析", placeholder: "例如：围绕二叉树遍历生成 8 道中等难度习题，包含单选、判断和简答，并给出逐题解析。", icon: "quiz", accent: "#3157d5", definition: quizDefinition },
  { resourceType: "flashcard", canonicalType: "flashcard", actionHint: "generate.flashcard", label: "闪卡", description: "生成便于复习和课堂抽查的卡片", placeholder: "例如：生成 12 张操作系统进程与线程闪卡，每张只考一个概念，答案简洁。", icon: "fact_check", accent: "#8b4bc2", definition: flashcardDefinition },
  { resourceType: "mind_map", canonicalType: "graph", actionHint: "generate.graph", label: "思维导图", description: "梳理主题层级与概念关系", placeholder: "例如：生成一张细胞呼吸思维导图，按阶段组织，标明发生场所、输入、输出和关键条件。", icon: "account_tree", accent: "#c0448a", definition: mindMapDefinition },
  { resourceType: "game", canonicalType: "game", actionHint: "generate.game", label: "课堂小游戏", description: "生成分类、配对或记忆互动", placeholder: "例如：设计一个英语不规则动词配对游戏，面向初一学生，共 10 组，完成后给出反馈。", icon: "play_circle", accent: "#26765b", definition: gameDefinition },
  { resourceType: "classroom", canonicalType: "classroom", actionHint: "generate.classroom", label: "AI 课堂", description: "根据需求生成教学视频", placeholder: "例如：用一段中文教学视频向初中生解释牛顿第二定律，展示力、质量和加速度的关系。", icon: "school", accent: "#126e82", definition: classroomDefinition },
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
    if (!item || ["lesson_plan", "blog"].includes(toolId) || seen.has(toolId)) continue;
    seen.add(toolId);
    selected.push(item);
  }
  return selected;
}
import { blogDefinition } from "./definitions/blog";
import { classroomDefinition } from "./definitions/classroom";
import { flashcardDefinition } from "./definitions/flashcard";
import { gameDefinition } from "./definitions/game";
import { lessonPlanDefinition } from "./definitions/lessonPlan";
import { mindMapDefinition } from "./definitions/mindMap";
import { quizDefinition } from "./definitions/quiz";
import { reportDefinition } from "./definitions/report";
