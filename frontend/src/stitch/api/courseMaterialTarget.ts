export type CourseMaterialTarget = {
  materialType: string;
  materialId: string;
};

function normalizeTargetValue(value: unknown): string {
  const normalized = String(value ?? "").trim();
  if (!normalized || normalized === "undefined" || normalized === "null") {
    return "";
  }
  return normalized;
}

export function courseMaterialKey(
  materialType: string,
  materialId: string,
): string {
  return `${encodeURIComponent(materialType)}:${encodeURIComponent(materialId)}`;
}

export function readCourseMaterialTarget(
  hash: string,
): CourseMaterialTarget | null {
  const query = String(hash || "").split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const materialType = normalizeTargetValue(params.get("material_type"));
  const materialId = normalizeTargetValue(params.get("material_id"));
  if (!materialType || !materialId) return null;
  return { materialType, materialId };
}
