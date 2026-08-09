import { blogDefinition, type BlogConfig } from "./blog";
import { lessonPlanDefinition, type LessonPlanConfig } from "./lessonPlan";
import { reportDefinition, type ReportConfig } from "./report";
import type { GenerationValidation } from "./types";
import type { GenerationResourceType } from "../generationRegistry";
import { quizDefinition, type QuizConfig } from "./quiz";
import { flashcardDefinition, type FlashcardConfig } from "./flashcard";
import { gameDefinition, type GameConfig } from "./game";
import { pptDefinition, type PptConfig } from "./ppt";
import { mindMapDefinition, type MindMapConfig } from "./mindMap";
import { classroomDefinition, type ClassroomConfig } from "./classroom";

export type TextGenerationConfig = ReportConfig | LessonPlanConfig | BlogConfig;

export function getTextDefinition(type: GenerationResourceType) {
  if (type === "report") return reportDefinition;
  if (type === "lesson_plan") return lessonPlanDefinition;
  if (type === "blog") return blogDefinition;
  return null;
}

export function getGenerationDefinition(type: GenerationResourceType) {
  return getTextDefinition(type)
    || (type === "quiz" ? quizDefinition : null)
    || (type === "flashcard" ? flashcardDefinition : null)
    || (type === "game" ? gameDefinition : null)
    || (type === "ppt" ? pptDefinition : null)
    || (type === "mind_map" ? mindMapDefinition : null)
    || (type === "classroom" ? classroomDefinition : null);
}

export function defaultGenerationConfig(type: GenerationResourceType): Record<string, unknown> {
  const definition = getGenerationDefinition(type);
  if (definition) return definition.defaultConfig();
  return { topic: "", audience: "本科生", requirements: "" };
}

export function validateGenerationConfig(type: GenerationResourceType, config: Record<string, unknown>): GenerationValidation {
  if (type === "report") return reportDefinition.validate(config as ReportConfig);
  if (type === "lesson_plan") return lessonPlanDefinition.validate(config as LessonPlanConfig);
  if (type === "blog") return blogDefinition.validate(config as BlogConfig);
  if (type === "quiz") return quizDefinition.validate(config as QuizConfig);
  if (type === "flashcard") return flashcardDefinition.validate(config as FlashcardConfig);
  if (type === "game") return gameDefinition.validate(config as GameConfig);
  if (type === "ppt") return pptDefinition.validate(config as PptConfig);
  if (type === "mind_map") return mindMapDefinition.validate(config as MindMapConfig);
  if (type === "classroom") return classroomDefinition.validate(config as ClassroomConfig);
  return String(config.topic || "").trim() ? {} : { topic: "请输入本次资源的主题" };
}

export function generationConfigTopic(config: Record<string, unknown>) {
  return String(config.topic || config.title || config.deckTitle || "").trim();
}

export function generationConfigAudience(config: Record<string, unknown>) {
  return String(config.audience || "本科生").trim();
}

export function generationConfigRequirements(config: Record<string, unknown>) {
  return String(config.specialRequirements || config.requirements || "").trim();
}
