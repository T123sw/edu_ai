import { canCourse, type CourseRole } from "../course/coursePermissions";
import type {
  CourseMaterial,
  MaterialPublicationResponse,
} from "./types";

export type MaterialPublicationPresentation = {
  visibilityLabel: "仅自己可见" | "课程共享";
  primaryAction: "publish" | "update" | null;
  primaryLabel: "发布到课程" | "更新发布" | "已发布" | null;
  canWithdraw: boolean;
};

export function getMaterialPublicationPresentation(
  material: CourseMaterial,
  role: CourseRole | null | undefined,
): MaterialPublicationPresentation {
  if (material.visibility !== "private") {
    return {
      visibilityLabel: "课程共享",
      primaryAction: null,
      primaryLabel: null,
      canWithdraw: canCourse(role, "manage_resources"),
    };
  }

  if (!canCourse(role, "manage_resources")) {
    return {
      visibilityLabel: "仅自己可见",
      primaryAction: null,
      primaryLabel: null,
      canWithdraw: false,
    };
  }

  const sourceVersion = Number(material.version || 0);
  const publishedVersion = Number(material.published_version || 0);
  if (!material.published_material_id) {
    return {
      visibilityLabel: "仅自己可见",
      primaryAction: "publish",
      primaryLabel: "发布到课程",
      canWithdraw: false,
    };
  }
  if (sourceVersion > publishedVersion) {
    return {
      visibilityLabel: "仅自己可见",
      primaryAction: "update",
      primaryLabel: "更新发布",
      canWithdraw: false,
    };
  }
  return {
    visibilityLabel: "仅自己可见",
    primaryAction: null,
    primaryLabel: "已发布",
    canWithdraw: false,
  };
}

export function applyPublicationResult(
  personalMaterials: readonly CourseMaterial[],
  sharedMaterials: readonly CourseMaterial[],
  result: MaterialPublicationResponse,
): { personal: CourseMaterial[]; shared: CourseMaterial[] } {
  const published = result.material;
  const personal = personalMaterials.map((material) => (
    material.material_id === result.source_material_id
      && material.material_type === published.material_type
      ? {
          ...material,
          published_material_id: published.material_id,
          published_version: published.published_from_version ?? material.version ?? null,
          published_at: published.published_at ?? null,
        }
      : material
  ));
  const existingIndex = sharedMaterials.findIndex((material) => (
    material.material_id === published.material_id
    && material.material_type === published.material_type
  ));
  const shared = existingIndex >= 0
    ? sharedMaterials.map((material, index) => (
        index === existingIndex ? published : material
      ))
    : [published, ...sharedMaterials];
  return { personal, shared };
}

export function applyPublicationWithdrawal(
  personalMaterials: readonly CourseMaterial[],
  sharedMaterials: readonly CourseMaterial[],
  publishedMaterial: CourseMaterial,
): { personal: CourseMaterial[]; shared: CourseMaterial[] } {
  const sourceMaterialId = publishedMaterial.published_from_material_id;
  const personal = personalMaterials.map((material) => (
    material.material_type === publishedMaterial.material_type
      && (
        material.material_id === sourceMaterialId
        || material.published_material_id === publishedMaterial.material_id
      )
      ? {
          ...material,
          published_material_id: null,
          published_version: null,
          published_at: null,
        }
      : material
  ));
  const shared = sharedMaterials.filter((material) => !(
    material.material_type === publishedMaterial.material_type
    && material.material_id === publishedMaterial.material_id
  ));
  return { personal, shared };
}
