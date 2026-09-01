import type { CourseMaterial } from "../api/types";

type QuizQuestion = NonNullable<CourseMaterial["questions"]>[number];

export function getQuizQuestions(material: CourseMaterial): QuizQuestion[] {
  if (Array.isArray(material.questions)) return material.questions;
  const content = material.content && typeof material.content === "object" && !Array.isArray(material.content)
    ? material.content as Record<string, unknown>
    : {};
  return Array.isArray(content.questions)
    ? content.questions.filter((question): question is QuizQuestion => Boolean(question && typeof question === "object" && !Array.isArray(question)))
    : [];
}
