import type { CourseMaterial } from "../api/types.ts";

const TEXT_TYPES = new Set(["report", "blog", "lesson_plan"]);

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function structuredContent(material: CourseMaterial): Record<string, unknown> {
  const content = record(material.content);
  switch (material.material_type) {
    case "quiz":
      return { questions: material.questions ?? content.questions ?? [] };
    case "flashcard":
      return { cards: material.flashcards ?? content.cards ?? [] };
    case "classroom":
      return { scenes: material.scenes ?? content.scenes ?? [] };
    default:
      return content;
  }
}

export function editableMaterialDraft(material: CourseMaterial): string {
  if (TEXT_TYPES.has(material.material_type)) {
    if (typeof material.content === "string") return material.content;
    return material.final_markdown
      || material.markdown
      || material.report_content
      || material.text
      || "";
  }
  return JSON.stringify(structuredContent(material), null, 2);
}

export function parseEditableMaterialDraft(
  material: CourseMaterial,
  draft: string,
): string | Record<string, unknown> {
  if (TEXT_TYPES.has(material.material_type)) return draft;
  try {
    const parsed = JSON.parse(draft) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("结构化资源必须是 JSON 对象");
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("JSON 格式不正确，请检查括号、引号和逗号");
    }
    throw error;
  }
}

export function isTextMaterial(material: CourseMaterial): boolean {
  return TEXT_TYPES.has(material.material_type);
}
