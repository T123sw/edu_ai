import type { CourseMaterial } from "../api/types";

function safeFilename(value: string): string {
  return value.replace(/[\\/:*?"<>|]+/g, "-").trim() || "课程资源";
}

export function materialExportFile(material: CourseMaterial, markdown: string) {
  const title = safeFilename(material.title || material.topic || material.material_id);
  if (["report", "blog", "lesson_plan"].includes(material.material_type)) {
    return {
      filename: `${title}.md`,
      content: markdown,
      mimeType: "text/markdown;charset=utf-8",
    };
  }
  const content = material.material_type === "quiz"
    ? { questions: material.questions ?? [] }
    : material.material_type === "flashcard"
      ? { cards: material.flashcards ?? [] }
      : material.content ?? {};
  return {
    filename: `${title}.json`,
    content: JSON.stringify(content, null, 2),
    mimeType: "application/json;charset=utf-8",
  };
}

export function downloadMaterialFile(material: CourseMaterial, markdown: string): void {
  const file = materialExportFile(material, markdown);
  const url = URL.createObjectURL(new Blob([file.content], { type: file.mimeType }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
