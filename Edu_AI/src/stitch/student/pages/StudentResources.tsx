import { useEffect, useMemo, useState } from "react";

import { StudentGenerationFactory } from "../tools/StudentGenerationFactory";
import {
  deleteCourseMaterial,
  getCourseMaterials,
  renameCourseMaterial,
} from "../../api/courses";
import {
  getCourseMaterialOpenTarget,
  getCourseMaterialTypeMeta,
} from "../../api/courseMaterialPresentation";
import type { CourseMaterial, CourseMaterialSpace } from "../../api/types";
import { useCourseRoute } from "../../course/CourseRouteProvider";
import { CourseMaterialArtifactPreview } from "../../pages/CourseMaterialArtifactPreview";
import { MaterialIcon } from "../../shared";
import type { GenerationToolId } from "../../shared/generation/generationCatalog";
import { buildStudentHash, readStudentLocation } from "../routes/studentRoutes";
import { saveRecentLearningVisit } from "./studentRecentLearning";
import "../styles/studentResources.css";

const REGENERATABLE = new Set<GenerationToolId>([
  "report", "ppt", "mind_map", "quiz", "classroom", "flashcard", "game",
]);

function resourceTitle(material: CourseMaterial) {
  return material.title || material.topic || "未命名资源";
}

function selectedTarget() {
  const query = window.location.hash.split("?")[1] || "";
  const params = new URLSearchParams(query);
  return {
    materialType: params.get("material_type"),
    materialId: params.get("material_id"),
  };
}

export function StudentResourcesPage() {
  const { courseId } = useCourseRoute();
  const [space, setSpace] = useState<CourseMaterialSpace>(() => readStudentLocation(window.location.hash).space ?? "mine");
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => selectedTarget().materialId);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [generatorTool, setGeneratorTool] = useState<GenerationToolId | null>(null);

  useEffect(() => {
    const sync = () => setSpace(readStudentLocation(window.location.hash).space ?? "mine");
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    if (!courseId) return;
    saveRecentLearningVisit(courseId, "student-resources");
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getCourseMaterials(courseId, { space, sort: "updated_desc" })
      .then((items) => {
        if (cancelled) return;
        setMaterials(items);
        const target = selectedTarget();
        setSelectedId((current) => {
          if (target.materialId && items.some((item) => item.material_id === target.materialId && (!target.materialType || item.material_type === target.materialType))) return target.materialId;
          if (current && items.some((item) => item.material_id === current)) return current;
          return items[0]?.material_id ?? null;
        });
      })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "资源加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, reload, space]);

  const visibleMaterials = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return materials;
    return materials.filter((item) => `${resourceTitle(item)} ${getCourseMaterialTypeMeta(item.material_type).label}`.toLocaleLowerCase().includes(normalized));
  }, [materials, query]);
  const active = visibleMaterials.find((item) => item.material_id === selectedId) ?? visibleMaterials[0] ?? null;

  function changeSpace(next: CourseMaterialSpace) {
    setNotice(null);
    setSelectedId(null);
    window.location.hash = buildStudentHash("student-resources", { courseId, space: next });
  }

  function open(material: CourseMaterial) {
    const target = getCourseMaterialOpenTarget({ ...material, course_id: material.course_id || courseId || undefined });
    if (target.kind === "route") window.location.hash = target.value;
    else setSelectedId(material.material_id);
  }

  async function rename(material: CourseMaterial) {
    if (!courseId || space !== "mine") return;
    const next = window.prompt("资源名称", resourceTitle(material))?.trim();
    if (!next || next === resourceTitle(material)) return;
    try {
      await renameCourseMaterial(courseId, material.material_type, material.material_id, next);
      setNotice("名称已更新");
      setReload((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重命名失败");
    }
  }

  async function remove(material: CourseMaterial) {
    if (!courseId || space !== "mine" || !window.confirm(`删除“${resourceTitle(material)}”？此操作不可撤销。`)) return;
    try {
      await deleteCourseMaterial(courseId, material.material_type, material.material_id);
      setNotice("个人资源已删除");
      setReload((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败");
    }
  }

  return (
    <div className="student-resources">
      <header className="student-resources__header">
        <div><p>资源管理</p><h2>个人生成与课程共享彼此隔离</h2><span>你生成的内容只属于个人；课程共享内容由教师发布，你可以查看和使用。</span></div>
        <label><MaterialIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索当前空间" /></label>
      </header>

      <nav className="student-space-tabs" aria-label="资源空间">
        <button type="button" aria-current={space === "mine" ? "page" : undefined} onClick={() => changeSpace("mine")}>个人生成</button>
        <button type="button" aria-current={space === "course" ? "page" : undefined} onClick={() => changeSpace("course")}>课程共享</button>
      </nav>

      {notice ? <p className="student-resource-notice">{notice}</p> : null}
      {error ? <div className="student-resource-error" role="alert"><span>{error}</span><button onClick={() => setReload((value) => value + 1)}>重试</button></div> : null}

      <div className="student-resources__workspace">
        <aside>
          <div className="student-resources__list-head"><strong>{space === "mine" ? "我的资源" : "教师发布"}</strong><span>{visibleMaterials.length}</span></div>
          {loading ? <p className="student-resource-state">正在加载…</p> : visibleMaterials.length === 0 ? <p className="student-resource-state">{space === "mine" ? "还没有个人资源，可在 AI 问答右侧生成。" : "教师暂未发布课程资源。"}</p> : (
            <div className="student-resources__list">
              {visibleMaterials.map((material) => {
                const meta = getCourseMaterialTypeMeta(material.material_type);
                return <article key={`${material.material_type}:${material.material_id}`} className={active?.material_id === material.material_id ? "is-active" : ""}>
                  <button className="student-resource-card__main" onClick={() => open(material)}><MaterialIcon name={meta.icon} /><span><strong>{resourceTitle(material)}</strong><small>{meta.label}{space === "course" && material.published_at ? ` · 发布于 ${new Date(material.published_at).toLocaleDateString("zh-CN")}` : ""}</small></span></button>
                  {space === "mine" ? <div className="student-resource-card__actions">
                    <button onClick={() => void rename(material)}>重命名</button>
                    {REGENERATABLE.has(material.material_type as GenerationToolId) ? <button onClick={() => setGeneratorTool(material.material_type as GenerationToolId)}>再次生成</button> : null}
                    <button className="is-danger" onClick={() => void remove(material)}>删除</button>
                  </div> : null}
                </article>;
              })}
            </div>
          )}
        </aside>
        <main>
          {active ? <><div className="student-resource-preview__head"><div><small>{getCourseMaterialTypeMeta(active.material_type).label}</small><h3>{resourceTitle(active)}</h3></div><span>{space === "mine" ? "仅自己可见" : "课程成员可见"}</span></div><CourseMaterialArtifactPreview material={active} /></> : <div className="student-resource-preview__empty"><MaterialIcon name="draft" /><p>选择一个资源查看内容</p></div>}
        </main>
      </div>

      {generatorTool && courseId ? <div className="student-generator-modal" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setGeneratorTool(null)}><section role="dialog" aria-modal="true" aria-label="再次生成资源"><button className="student-generator-modal__close" aria-label="关闭" onClick={() => setGeneratorTool(null)}><MaterialIcon name="close" /></button><StudentGenerationFactory courseId={courseId} allowedTools={[generatorTool]} selectedDocumentIds={[]} /></section></div> : null}
    </div>
  );
}
