import type { CourseMaterialSpace } from "../../api/types";

export type StudentResourceAction = "preview" | "download" | "rename" | "delete" | "regenerate";
export type StudentClassroomAction = "create" | "play" | "rename" | "delete";

const RESOURCE_ACTIONS: Record<CourseMaterialSpace, readonly StudentResourceAction[]> = {
  mine: ["preview", "download", "rename", "delete", "regenerate"],
  course: ["preview", "download"],
};

const CLASSROOM_ACTIONS: Record<CourseMaterialSpace, readonly StudentClassroomAction[]> = {
  mine: ["create", "play", "rename", "delete"],
  course: ["play"],
};

export function getStudentResourceActions(space: CourseMaterialSpace) {
  return RESOURCE_ACTIONS[space];
}

export function getStudentClassroomActions(space: CourseMaterialSpace) {
  return CLASSROOM_ACTIONS[space];
}

export function readStudentResourceSpace(hash: string): CourseMaterialSpace {
  const query = hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : "";
  return new URLSearchParams(query).get("space") === "course" ? "course" : "mine";
}
