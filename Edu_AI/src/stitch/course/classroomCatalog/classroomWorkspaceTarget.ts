export type ClassroomWorkspaceTarget =
  | { kind: "overview"; nodeId: string | null }
  | { kind: "catalog_resource"; nodeId: string; resourceId: string }
  | { kind: "personal_classroom"; classroomId: string };

export function readWorkspaceTarget(hash: string): ClassroomWorkspaceTarget {
  const query = hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const classroomId = params.get("personal_classroom_id")?.trim() || "";
  const nodeId = params.get("node_id")?.trim() || "";
  const resourceId = params.get("resource_id")?.trim() || "";

  if (classroomId && (nodeId || resourceId)) {
    return { kind: "overview", nodeId: null };
  }
  if (classroomId) {
    return { kind: "personal_classroom", classroomId };
  }
  if (nodeId && resourceId) {
    return { kind: "catalog_resource", nodeId, resourceId };
  }
  return { kind: "overview", nodeId: nodeId || null };
}

export function buildWorkspaceHash(
  role: "teacher" | "student",
  courseId: string,
  target: ClassroomWorkspaceTarget,
): string {
  const route = role === "student" ? "student-classroom" : "teacher-classroom-studio";
  const params = new URLSearchParams({ course_id: courseId });

  if (target.kind === "personal_classroom") {
    params.set("personal_classroom_id", target.classroomId);
  } else {
    if (target.nodeId) params.set("node_id", target.nodeId);
    if (target.kind === "catalog_resource") params.set("resource_id", target.resourceId);
  }

  return `#${route}?${params.toString()}`;
}
