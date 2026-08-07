import type { CourseMaterial } from "./types";

export type CourseMaterialPage = {
  items: CourseMaterial[];
  count: number;
  total: number;
  limit: number;
  offset: number;
};

export function unwrapCourseMaterials(
  payload: CourseMaterial[] | CourseMaterialPage,
): CourseMaterial[] {
  return Array.isArray(payload) ? payload : payload.items;
}
