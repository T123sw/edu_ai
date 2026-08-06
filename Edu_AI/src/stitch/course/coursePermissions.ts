export type CourseRole = "owner" | "editor" | "viewer";

export type CourseCapability =
  | "read"
  | "edit"
  | "generate"
  | "manage_resources"
  | "manage_members"
  | "delete_course";

const capabilities: Record<CourseRole, ReadonlySet<CourseCapability>> = {
  viewer: new Set(["read"]),
  editor: new Set(["read", "edit", "generate", "manage_resources"]),
  owner: new Set([
    "read",
    "edit",
    "generate",
    "manage_resources",
    "manage_members",
    "delete_course",
  ]),
};

export function canCourse(
  role: CourseRole | null | undefined,
  capability: CourseCapability,
): boolean {
  return role ? capabilities[role].has(capability) : false;
}
