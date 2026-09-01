import { apiRequest } from "./client";
import type { ClassroomCatalog } from "./types";


export function getClassroomCatalog(courseId: string) {
  return apiRequest<ClassroomCatalog>(
    `/api/courses/${encodeURIComponent(courseId)}/classroom-catalog`,
  );
}
