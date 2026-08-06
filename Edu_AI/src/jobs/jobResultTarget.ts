import { buildClassroomPlayerHash } from "../openmaic/classroomGenerationFlow";
import { buildTeacherCourseHash } from "../stitch/teacherRoutes";
import type { JobRecord } from "./types";

export function getJobResultHash(job: JobRecord): string | null {
  const result = job.result_ref;
  const courseId = String(result?.course_id || job.course_id || "").trim();
  const materialType = String(result?.material_type || "").trim();
  const materialId = String(
    result?.material_id || result?.classroom_id || "",
  ).trim();

  if (!courseId || !materialId) return null;
  if (
    materialType === "classroom"
    || result?.resource_type === "classroom_video"
  ) {
    return buildClassroomPlayerHash(courseId, materialId);
  }
  if (result?.resource_type !== "course_material" || !materialType) {
    return null;
  }
  return buildTeacherCourseHash("resources", courseId, {
    material_type: materialType,
    material_id: materialId,
  });
}
