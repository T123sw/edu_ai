import { useEffect, useState } from "react";
import type { CourseMaterial } from "../api/types";
import { getCourseMaterial } from "../api/courses";
import { useAuthSession } from "../authSession";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { createRevisionIntent, dispatchRevisionIntent, type ArtifactRevisionReference } from "./intent";

export function EditReference({ reference, onClose }: { reference: ArtifactRevisionReference; onClose: () => void }) {
  return <div role="status" className="flex min-w-0 flex-wrap items-center gap-2 rounded-xl border p-3">
    <span className="min-w-0 break-words">正在修改：《{reference.title || reference.artifact_id}》 · 第 {reference.version_id.replace(/^v/, "")} 版</span>
    <button type="button" onClick={onClose} aria-label="取消资料引用" className="ml-auto min-h-10 min-w-10">×</button>
  </div>;
}

export function RevisionResult({ reference, summary, changes, onView, onContinue, onRestore }: {
  reference: ArtifactRevisionReference; summary: string;
  changes: Array<{ path: Array<string | number>; before: string; after: string }>;
  onView: () => void; onContinue: () => void; onRestore?: () => void;
}) {
  return <section aria-label="资料修改结果" className="min-w-0 rounded-xl border p-3">
    <p className="break-words">已保存《{reference.title || reference.artifact_id}》第 {reference.version_id.replace(/^v/, "")} 版</p>
    <p>{summary}</p>
    <div className="flex flex-wrap gap-3"><button type="button" onClick={onView}>查看新版</button><button type="button" onClick={onContinue}>继续修改</button>{onRestore && <button type="button" onClick={onRestore}>恢复旧版</button>}</div>
    <details><summary>查看修改</summary>{changes.map((change, index) => <div key={index}><p className="whitespace-pre-wrap break-words"><del>{change.before}</del></p><p className="whitespace-pre-wrap break-words"><ins>{change.after}</ins></p></div>)}</details>
  </section>;
}

export function RevisionButton({ material, disabled = false }: { material: CourseMaterial; disabled?: boolean }) {
  const { user } = useAuthSession();
  const intent = createRevisionIntent(material, user?.username || "");
  if (!intent) return null;
  return <button type="button" disabled={disabled} className="rounded-full border bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-50" onClick={() => {
    dispatchRevisionIntent(intent);
    window.location.hash = buildRoleCourseHash(user?.role, "ai", material.course_id);
  }}>让 AI 修改</button>;
}

export function GenerationRevisionButton({ courseId, materialType, materialId }: { courseId: string; materialType: string; materialId: string }) {
  const { user } = useAuthSession();
  const [material, setMaterial] = useState<CourseMaterial | null>(null);
  useEffect(() => {
    let active = true;
    setMaterial(null);
    void getCourseMaterial(courseId, materialType, materialId).then((value) => { if (active) setMaterial(value); }).catch(() => { if (active) setMaterial(null); });
    return () => { active = false; };
  }, [courseId, materialType, materialId, user?.username]);
  return material ? <RevisionButton material={material} /> : null;
}
