import type { JobRecord } from "../../jobs/types";
import {
  getGenerationResource,
  type GenerationResourceType,
} from "./generationRegistry";

const RESOURCE_TYPE_BY_JOB_KIND: Record<string, GenerationResourceType> = {
  generate_report: "report",
  generate_lesson_plan: "lesson_plan",
  generate_blog: "blog",
  generate_quiz: "quiz",
  generate_flashcard: "flashcard",
  generate_graph: "mind_map",
  generate_game: "game",
  generate_classroom: "classroom",
};

const SUBJECT_FIELDS = [
  "topic",
  "title",
  "subject",
  "requirement",
  "prompt",
  "name",
] as const;

export function presentGenerationJob(job: JobRecord) {
  const summaryType = String(job.input_summary?.resource_type || "").trim();
  const resourceType = RESOURCE_TYPE_BY_JOB_KIND[job.kind]
    || (summaryType in RESOURCE_TYPE_BY_JOB_KIND
      ? RESOURCE_TYPE_BY_JOB_KIND[summaryType]
      : summaryType as GenerationResourceType);
  const resource = getGenerationResource(resourceType);
  const subject = SUBJECT_FIELDS
    .map((field) => String(job.input_summary?.[field] || "").trim())
    .find(Boolean);

  return {
    title: subject || resource.label,
    icon: resource.icon,
    accent: resource.accent,
  };
}
