export type ClassroomSpace = "mine" | "course";

export function buildClassroomListPath(
  courseId: string,
  space: ClassroomSpace,
) {
  return `/api/courses/${encodeURIComponent(courseId)}/classrooms?space=${space}`;
}
