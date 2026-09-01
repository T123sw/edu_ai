import { useCallback, useEffect, useRef, useState } from "react";
import { recordReadingActivity } from "../../api/resourceLearning";
import type { ClassroomCatalogProgress, ClassroomCatalogResource, ResourceLearningProgress } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { CourseMaterialArtifactPreview } from "../../pages/CourseMaterialArtifactPreview";
import { StudentResourceProgressPanel } from "./StudentResourceProgressPanel";

type Props = { courseId: string; resource: ClassroomCatalogResource; onProgress?: (progress: ResourceLearningProgress) => void };

function activityEventId(resourceId: string, version: number, action: "opened" | "completed") {
  const key = `classroom-catalog-activity:${resourceId}:${version}:${action}`;
  try {
    const stored = sessionStorage.getItem(key);
    if (stored) return stored;
    const created = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem(key, created);
    return created;
  } catch { return `${key}:${Date.now()}`; }
}

export function StudentReadingView({ courseId, resource, onProgress }: Props) {
  const version = resource.approved_version ?? resource.current_version ?? 0;
  const [progress, setProgress] = useState<ClassroomCatalogProgress | ResourceLearningProgress | null>(resource.progress ?? null);
  const [sync, setSync] = useState<"idle" | "syncing" | "failed">("idle");
  const opened = useRef(false);
  const send = useCallback(async (action: "opened" | "completed") => {
    if (!version) return;
    setSync("syncing");
    try {
      const next = await recordReadingActivity(courseId, resource.material_id, version, { event_id: activityEventId(resource.material_id, version, action), action, occurred_at: new Date().toISOString() });
      setProgress(next); setSync("idle"); onProgress?.(next);
    } catch { setSync("failed"); }
  }, [courseId, onProgress, resource.material_id, version]);
  useEffect(() => { if (!opened.current) { opened.current = true; void send("opened"); } }, [send]); // explicit open evidence only
  return <section className="student-reading-view">
    <header><div><p className="curriculum-node-overview__eyebrow">学习指南</p><h2>{resource.resource?.title || "学习指南"}</h2></div><StudentResourceProgressPanel progress={progress} /></header>
    {resource.resource ? <CourseMaterialArtifactPreview material={resource.resource} /> : <p className="catalog-panel-message">当前文档暂时无法预览。</p>}
    <footer><span>{sync === "failed" ? "进度暂时无法同步" : sync === "syncing" ? "正在同步进度…" : "阅读内容后，请主动确认完成。"}</span>
      <button type="button" className="catalog-primary-action" disabled={progress?.status === "completed" || sync === "syncing"} onClick={() => void send("completed")}><MaterialIcon name="check_circle" />{progress?.status === "completed" ? "已完成阅读" : "完成阅读"}</button>
    </footer>
  </section>;
}
