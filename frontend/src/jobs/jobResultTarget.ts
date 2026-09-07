import { buildClassroomPlayerHash } from "../openmaic/classroomGenerationFlow";
import { buildRoleCourseHash } from "../stitch/shared/routes/roleCourseRouteResolver";
import { buildTeacherCourseHash } from "../stitch/teacherRoutes";
import type { JobRecord } from "./types";

export function getJobResultHash(job: JobRecord): string | null {
  const result = job.result_ref;
  const courseId = String(result?.course_id || job.course_id || "").trim();
  const materialType = String(result?.material_type || "").trim();
  const materialId = String(
    result?.material_id || result?.classroom_id || "",
  ).trim();

  if (result?.resource_type === "artifact_conversation" && courseId) {
    return buildRoleCourseHash(result.actor_role === 'student' ? 'student' : 'teacher', 'ai', courseId)
      + '&conversation_id=' + encodeURIComponent(String(result.conversation_id || ''));
  }
  if (result?.resource_type === "artifact_revision" && courseId && materialId) {
    return buildRoleCourseHash(result.actor_role === 'student' ? 'student' : 'teacher', 'resources', courseId,
      { material_type: materialType, material_id: materialId });
  }
  if (!courseId || !materialId) return null;
  if (
    materialType === "classroom"
    || result?.resource_type === "classroom_video"
  ) {
    return buildClassroomPlayerHash(courseId, materialId);
  }
  if (!["course_material", "artifact_revision"].includes(String(result?.resource_type)) || !materialType) {
    return null;
  }
  return buildTeacherCourseHash("resources", courseId, {
    material_type: materialType,
    material_id: materialId,
  });
}
