import { GenerationFactory } from "../../../components/generation/GenerationFactory";
import type { GenerationToolId } from "../../shared/generation/generationCatalog";
import { buildStudentHash } from "../routes/studentRoutes";

export function StudentGenerationFactory({
  courseId,
  allowedTools,
  selectedDocumentIds,
}: {
  courseId: string;
  allowedTools: readonly GenerationToolId[];
  selectedDocumentIds: readonly string[];
}) {
  return (
    <GenerationFactory
      courseId={courseId}
      allowedTools={allowedTools}
      selectedDocumentIds={selectedDocumentIds}
      sourceLibraries={["course", "personal"]}
      resultHref={({ courseId: resultCourseId, materialType, materialId }) => buildStudentHash("student-resources", {
        courseId: resultCourseId || courseId,
        space: "mine",
        materialType,
        materialId,
      })}
    />
  );
}
