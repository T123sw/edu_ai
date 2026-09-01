export type GenerationToolId =
  | "report"
  | "mind_map"
  | "quiz"
  | "classroom"
  | "lesson_plan"
  | "blog"
  | "flashcard"
  | "game";

const generationToolIds = new Set<GenerationToolId>([
  "report", "mind_map", "quiz", "classroom",
  "lesson_plan", "blog", "flashcard", "game",
]);

export function isGenerationToolId(value: unknown): value is GenerationToolId {
  return typeof value === "string" && generationToolIds.has(value as GenerationToolId);
}

export function sanitizeGenerationCatalog(
  tools: readonly Array<{ tool_id?: unknown }>,
): GenerationToolId[] {
  const result: GenerationToolId[] = [];
  const seen = new Set<GenerationToolId>();
  for (const tool of tools) {
    if (!isGenerationToolId(tool.tool_id) || seen.has(tool.tool_id)) continue;
    seen.add(tool.tool_id);
    result.push(tool.tool_id);
  }
  return result;
}
