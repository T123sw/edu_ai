import type { ClassroomMaterial } from "../../api/types";

export type MyClassroomStatus = "ready" | "generating" | "failed" | "empty";

export type MyClassroomItem = {
  id: string;
  title: string;
  updatedAt: string;
  status: MyClassroomStatus;
  material: ClassroomMaterial;
};

function resolveStatus(material: ClassroomMaterial): MyClassroomStatus {
  if (material.video_status === "failed") return "failed";
  if (material.video_status === "queued" || material.video_status === "running") {
    return "generating";
  }
  if ((material.scenes?.length ?? 0) > 0 || material.video_url) return "ready";
  return "empty";
}

export function presentMyClassrooms(materials: ClassroomMaterial[]): MyClassroomItem[] {
  return materials
    .filter((material) => material.material_type === "classroom")
    .map((material) => ({
      id: material.material_id,
      title: material.title?.trim() || "未命名课堂",
      updatedAt: material.updated_at || material.created_at || "",
      status: resolveStatus(material),
      material,
    }))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}
