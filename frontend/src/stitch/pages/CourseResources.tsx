import { RevisionHistoryDialog } from "../../components/teacher/RevisionHistoryDialog";
import { createRevisionIntent, type ArtifactRevisionReference } from "../artifactRevision/intent";
import { RevisionButton } from "../artifactRevision/components";
import { useEffect, useMemo, useState } from "react";
import {
  backendCourseToSummary,
  deleteCourseMaterial,
  getCourseMaterial,
  getCourseMaterials,
  getKnowledgeGraph,
  pinCourseMaterial,
  renameCourseMaterial,
} from "../api/courses";
import {
  getCourseMaterialOpenTarget,
  getCourseMaterialTypeMeta,
} from "../api/courseMaterialPresentation";
import {
  courseMaterialKey,
  readCourseMaterialTarget,
} from "../api/courseMaterialTarget";
import type { CourseMaterial, KnowledgeGraphNode } from "../api/types";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  defaultCourse,
  routes,
  useAppShell,
} from "../shared";
import { useAuthSession } from "../authSession";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { CourseMaterialArtifactPreview } from "./CourseMaterialArtifactPreview";
import { ResourceKnowledgeDirectory } from "./ResourceKnowledgeDirectory";
import "./courseResources.css";
import { MaterialContentEditor } from "./MaterialContentEditor";

type ResourceSort = "recent" | "title";

const EDITABLE_MATERIAL_TYPES = new Set([
  "report",
  "blog",
  "lesson_plan",
  "graph",
]);

function getMaterialTitle(material: CourseMaterial): string {
  return material.title || material.topic || "未命名资源";
}

function getMaterialTimestamp(material: CourseMaterial): number {
  const parsed = Date.parse(material.updated_at || material.created_at || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMaterialDate(material: CourseMaterial): string {
  const timestamp = getMaterialTimestamp(material);
  if (!timestamp) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(timestamp);
}

export function CourseResourcesPage() {
  const { user } = useAuthSession();
  const { selectedCourse } = useAppShell();
  const { course: routeCourse, courseId } = useCourseRoute();
  const course = routeCourse?.id === courseId
    ? backendCourseToSummary(routeCourse)
    : selectedCourse?.id === courseId
      ? selectedCourse
      : { ...defaultCourse, id: courseId || defaultCourse.id };
  const [revisionHistory, setRevisionHistory] = useState<ArtifactRevisionReference | null>(null);
  const [personalMaterials, setPersonalMaterials] = useState<CourseMaterial[]>([]);
  const [knowledgeRoot, setKnowledgeRoot] = useState<KnowledgeGraphNode | null>(null);
  const [directoryError, setDirectoryError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [sort, setSort] = useState<ResourceSort>("recent");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingContent, setEditingContent] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const materials = personalMaterials;
  useEffect(() => {
    let cancelled = false;
    setKnowledgeRoot(null);
    setDirectoryError(false);
    void getKnowledgeGraph(course.id).then((data) => {
      if (!cancelled) setKnowledgeRoot(data.root);
    }).catch(() => { if (!cancelled) setDirectoryError(true); });
    return () => { cancelled = true; };
  }, [course.id, reloadToken]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        setRecoveryError(null);
        const personalData = await getCourseMaterials(course.id, {
          space: "mine",
          sort: sort === "recent" ? "updated_desc" : "name_asc",
        });
        const requestedTarget = readCourseMaterialTarget(
          typeof window === "undefined" ? "" : window.location.hash,
        );
        let nextPersonal = personalData;
        let requestedKey: string | null = null;
        if (requestedTarget) {
          requestedKey = courseMaterialKey(
            requestedTarget.materialType,
            requestedTarget.materialId,
          );
          const listed = personalData.some(
            (item) =>
              courseMaterialKey(item.material_type, item.material_id)
              === requestedKey,
          );
          if (!listed) {
            try {
              const detail = await getCourseMaterial(
                course.id,
                requestedTarget.materialType,
                requestedTarget.materialId,
              );
              if (detail.visibility !== "private") {
                throw new Error("Material is outside the personal resource space");
              }
              nextPersonal = [detail, ...personalData];
            } catch {
              if (!cancelled) {
                setPersonalMaterials(personalData);
                setActiveKey(null);
                setRecoveryError("该资源不在个人资源中或无权访问");
              }
              return;
            }
          }
        }
        if (!cancelled) {
          setPersonalMaterials(nextPersonal);
          if (requestedKey) {
            setActiveKey(requestedKey);
          } else {
            setActiveKey((current) =>
              nextPersonal.some(
                (item) =>
                  courseMaterialKey(item.material_type, item.material_id)
                  === current,
              )
                ? current
                : (
                  nextPersonal[0]
                    ? courseMaterialKey(
                        nextPersonal[0].material_type,
                        nextPersonal[0].material_id,
                      )
                    : null
                ),
            );
          }
        }
      } catch {
        if (!cancelled) {
          setError("资源加载失败，请稍后重试");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [course.id, reloadToken, sort]);

  const filteredMaterials = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const filtered = materials.filter((material) => {
      if (pinnedOnly && !material.is_pinned) return false;
      if (!normalizedQuery) return true;
      const searchText = [
        getMaterialTitle(material),
        material.summary,
        getCourseMaterialTypeMeta(material.material_type).label,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      return searchText.includes(normalizedQuery);
    });

    return filtered;
  }, [materials, pinnedOnly, query]);

  useEffect(() => {
    if (
      activeKey &&
      filteredMaterials.some(
        (material) =>
          courseMaterialKey(material.material_type, material.material_id)
          === activeKey,
      )
    ) {
      return;
    }
    if (recoveryError) return;
    const first = filteredMaterials[0];
    setActiveKey(
      first ? courseMaterialKey(first.material_type, first.material_id) : null,
    );
  }, [activeKey, filteredMaterials, recoveryError]);

  useEffect(() => {
    setEditingTitle(false);
    setEditingContent(false);
    setActionError(null);
    setActionNotice(null);
  }, [activeKey]);

  const activeMaterial =
    recoveryError
      ? null
      : (
        filteredMaterials.find(
          (item) =>
            courseMaterialKey(item.material_type, item.material_id)
            === activeKey,
        )
        ?? filteredMaterials[0]
        ?? null
      );

  function openMaterial(material: CourseMaterial) {
    const target = getCourseMaterialOpenTarget(material);
    if (target.kind === "route") {
      window.location.hash = target.value;
      return;
    }
    setRecoveryError(null);
    setActiveKey(courseMaterialKey(material.material_type, target.value));
  }

  async function togglePinned(material: CourseMaterial) {
    setActionBusy(true);
    setActionError(null);
    try {
      const updated = await pinCourseMaterial(
        course.id,
        material.material_type,
        material.material_id,
        !material.is_pinned,
      );
      setPersonalMaterials((current) => current.map((item) => (
        item.material_id === updated.material_id
        && item.material_type === updated.material_type
          ? updated
          : item
      )));
    } catch {
      setActionError("置顶操作失败，请稍后重试");
    } finally {
      setActionBusy(false);
    }
  }

  async function saveTitle(material: CourseMaterial) {
    const title = titleDraft.trim();
    if (!title) {
      setActionError("资源名称不能为空");
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      const updated = await renameCourseMaterial(
        course.id,
        material.material_type,
        material.material_id,
        title,
      );
      setPersonalMaterials((current) => current.map((item) => (
        item.material_id === updated.material_id
        && item.material_type === updated.material_type
          ? updated
          : item
      )));
      setEditingTitle(false);
      setReloadToken((current) => current + 1);
    } catch {
      setActionError("重命名失败，请稍后重试");
    } finally {
      setActionBusy(false);
    }
  }

  async function removeMaterial(material: CourseMaterial) {
    if (!window.confirm(`确定删除“${getMaterialTitle(material)}”及其全部导出文件吗？`)) {
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      await deleteCourseMaterial(
        course.id,
        material.material_type,
        material.material_id,
      );
      setPersonalMaterials((current) => current.filter((item) => !(
        item.material_id === material.material_id
        && item.material_type === material.material_type
      )));
    } catch {
      setActionError("删除资源失败，请稍后重试");
    } finally {
      setActionBusy(false);
    }
  }

  const activeMeta = activeMaterial
    ? getCourseMaterialTypeMeta(activeMaterial.material_type)
    : null;
  const previewSupported =
    activeMaterial
    && activeMaterial.material_type !== "classroom"
    && activeMeta?.known;

  return (
    <AppSurface className="course-resources flex min-h-[calc(100vh-var(--course-header-height))] min-[900px]:h-[calc(100vh-var(--course-header-height))] min-[900px]:overflow-hidden">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden min-[900px]:overflow-y-hidden">
        <div className="grid min-h-0 min-w-0 flex-1 gap-5 p-5 min-[900px]:grid-cols-[clamp(310px,22vw,360px)_minmax(0,1fr)] min-[900px]:overflow-hidden">
          <section aria-label="知识点目录" className="resource-directory flex max-h-[360px] min-h-0 min-w-0 flex-col overflow-hidden min-[900px]:max-h-none">
            <div className="resource-directory-heading"><h1>知识点目录</h1><span>{filteredMaterials.length} 份资源</span></div>
            <div className="resource-directory-tools">
              <label className="resource-directory-search">
                <MaterialIcon name="search" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索资源" aria-label="搜索资源" />
              </label>
              <div className="resource-directory-options">
                <select aria-label="资源排序" value={sort} onChange={(event) => setSort(event.target.value as ResourceSort)}>
                  <option value="recent">最近更新</option><option value="title">按名称</option>
                </select>
                <label><input type="checkbox" checked={pinnedOnly} onChange={(event) => setPinnedOnly(event.target.checked)} />仅看置顶</label>
              </div>
            </div>
            {directoryError ? <p className="px-3 pb-3 text-xs text-(--muted-text)">目录暂时无法加载，仍可浏览资源。<button type="button" className="ml-2 underline" onClick={() => setReloadToken((value) => value + 1)}>重试</button></p> : null}
            {loading ? (
              <GlassPanel className="border border-(--shell-border) bg-white/90 p-6 text-sm text-(--muted-text)">
                正在加载资源...
              </GlassPanel>
            ) : error ? (
              <GlassPanel className="border border-rose-200 bg-white/90 p-6">
                <p className="text-sm font-semibold text-rose-600">{error}</p>
                <button
                  type="button"
                  onClick={() => setReloadToken((current) => current + 1)}
                  className="mt-4 rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white"
                >
                  重新加载
                </button>
              </GlassPanel>
            ) : materials.length === 0 ? (
              <GlassPanel className="border border-(--shell-border) bg-white/90 p-6">
                <h2 className="font-bold text-(--app-text)">你还没有个人资源</h2>
                <p className="mt-2 text-sm leading-6 text-(--muted-text)">
                  在工作台创建教学内容后，即可在这里查看。
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <a
                    href={buildRoleCourseHash(user?.role, routes.ai, course.id)}
                    className="rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white"
                  >
                    前往工作台
                  </a>
                  <a
                    href={buildRoleCourseHash(
                      user?.role,
                      routes.classroomStudio,
                      course.id,
                    )}
                    className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold text-(--accent-strong)"
                  >
                    创建 AI 课堂
                  </a>
                </div>
              </GlassPanel>
            ) : filteredMaterials.length === 0 ? (
              <GlassPanel className="border border-(--shell-border) bg-white/90 p-6 text-sm text-(--muted-text)">
                没有符合当前筛选条件的资源。
              </GlassPanel>
            ) : (
              <ResourceKnowledgeDirectory
                key={course.id}
                root={knowledgeRoot}
                searching={Boolean(query.trim()) || pinnedOnly}
                materials={filteredMaterials}
                activeKey={activeKey}
                onSelect={(material) => {
                  setRecoveryError(null);
                  setActiveKey(courseMaterialKey(material.material_type, material.material_id));
                }}
              />
            )}
          </section>

          <section className="min-h-0 min-w-0">
            <GlassPanel className="flex h-full min-h-0 min-w-0 flex-col border border-(--shell-border) bg-white/90 p-6">
              {recoveryError ? (
                <div className="flex h-full items-center justify-center">
                  <div className="max-w-md rounded-[22px] border border-rose-200 bg-rose-50 p-6 text-center">
                    <MaterialIcon
                      name="error"
                      className="text-3xl text-rose-500"
                    />
                    <h2 className="mt-3 font-black text-rose-700">
                      无法打开资源
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-rose-600">
                      {recoveryError}
                    </p>
                  </div>
                </div>
              ) : activeMaterial && activeMeta ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-(--shell-border) pb-4">
                    <div className="min-w-0">
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">
                        {activeMeta.label}
                      </p>
                      {editingTitle ? (
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <input
                            value={titleDraft}
                            onChange={(event) => setTitleDraft(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") void saveTitle(activeMaterial);
                              if (event.key === "Escape") setEditingTitle(false);
                            }}
                            autoFocus
                            maxLength={200}
                            className="h-11 min-w-64 rounded-2xl border border-(--accent-border) bg-white px-4 text-lg font-bold outline-hidden"
                          />
                          <button
                            type="button"
                            disabled={actionBusy}
                            onClick={() => void saveTitle(activeMaterial)}
                            className="rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
                          >
                            保存
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingTitle(false)}
                            className="rounded-full border border-(--shell-border) bg-white px-4 py-2 text-sm font-bold"
                          >
                            取消
                          </button>
                        </div>
                      ) : (
                        <h2 className="mt-2 break-words text-2xl font-black text-(--accent-strong)">
                          {getMaterialTitle(activeMaterial)}
                        </h2>
                      )}
                      <p className="mt-2 text-xs text-(--muted-text)">{[activeMaterial.topic, getMaterialTimestamp(activeMaterial) ? `更新于 ${formatMaterialDate(activeMaterial)}` : null].filter(Boolean).join(" · ")}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs">第 {activeMaterial.version || 1} 版</span>
                      {Number(activeMaterial.version) > 1 && <button type="button" disabled={actionBusy}
                        onClick={() => { const intent = createRevisionIntent(activeMaterial, user?.username || ''); if (intent) setRevisionHistory(intent.reference); }}
                        className="rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-bold">历史版本与原版副本</button>}
                      {revisionHistory && <RevisionHistoryDialog reference={revisionHistory} onClose={() => setRevisionHistory(null)}
                        onRestored={() => { setRevisionHistory(null); setReloadToken(value => value + 1); }} />}
                      <RevisionButton material={activeMaterial} disabled={actionBusy} />
                      {EDITABLE_MATERIAL_TYPES.has(activeMaterial.material_type) ? (
                        <button
                          type="button"
                          disabled={actionBusy}
                          onClick={() => setEditingContent((current) => !current)}
                          className="rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-bold text-(--accent-strong) disabled:opacity-50"
                        >
                          {editingContent ? "返回预览" : "编辑内容"}
                        </button>
                      ) : null}
                      <details key={activeKey} className="resource-more"><summary>更多操作</summary><div className="resource-more-menu">
                      <button
                        type="button"
                        disabled={actionBusy}
                        onClick={() => void togglePinned(activeMaterial)}
                        className="rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-bold text-(--accent-strong) disabled:opacity-50"
                      >
                        {activeMaterial.is_pinned ? "取消置顶" : "置顶"}
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy}
                        onClick={() => {
                          setTitleDraft(getMaterialTitle(activeMaterial));
                          setEditingTitle(true);
                        }}
                        className="rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-bold text-(--accent-strong) disabled:opacity-50"
                      >
                        重命名
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy}
                        onClick={() => void removeMaterial(activeMaterial)}
                        className="rounded-full border border-rose-200 bg-white px-4 py-2.5 text-sm font-bold text-rose-600 disabled:opacity-50"
                      >
                        删除
                      </button>
                      </div></details>
                      {activeMaterial.material_type === "classroom" ? (
                        <button
                          type="button"
                          onClick={() => openMaterial(activeMaterial)}
                          className="inline-flex items-center gap-2 rounded-full bg-(--accent) px-5 py-3 text-sm font-bold text-white"
                        >
                          <MaterialIcon name="play_circle" className="text-base" />
                          打开课堂
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {actionError ? (
                    <p className="mt-3 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
                      {actionError}
                    </p>
                  ) : null}

                  {actionNotice ? (
                    <p className="mt-3 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                      {actionNotice}
                    </p>
                  ) : null}

                  <div key={activeKey} className="resource-document mt-5 min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden pr-2">
                    {editingContent ? (
                      <MaterialContentEditor
                        courseId={course.id}
                        material={activeMaterial}
                        onCancel={() => setEditingContent(false)}
                        onSaved={(updated) => {
                          const replace = (items: CourseMaterial[]) => items.map((item) => (
                            item.material_id === updated.material_id
                            && item.material_type === updated.material_type
                              ? updated
                              : item
                          ));
                          setPersonalMaterials(replace);
                          setEditingContent(false);
                          setActionNotice("资源内容已保存");
                        }}
                      />
                    ) : activeMaterial.material_type === "classroom" ? (
                      <div className="resource-classroom-cover">
                        <MaterialIcon name="play_circle" className="text-5xl text-(--accent)" />
                        <h3>{getMaterialTitle(activeMaterial)}</h3>
                        <p>{activeMaterial.scenes_count ?? activeMaterial.scenes?.length ?? 0} 个教学场景</p>
                        <button type="button" onClick={() => openMaterial(activeMaterial)}>进入 AI 课堂</button>
                      </div>
                    ) : previewSupported ? (
                      <CourseMaterialArtifactPreview material={activeMaterial} />
                    ) : (
                      <div className="rounded-2xl border border-dashed border-(--shell-border) bg-(--surface-subtle) p-6">
                        <h3 className="font-bold text-(--app-text)">
                          暂无专用预览
                        </h3>
                        <p className="mt-2 text-sm leading-6 text-(--muted-text)">
                          此资源暂时无法在线预览，请选择其他资源。
                        </p>
                        <dl className="mt-5 grid gap-3 text-sm">
                          <div>
                            <dt className="text-(--muted-text)">资源类型</dt>
                            <dd className="mt-1 font-semibold text-(--app-text)">
                              {activeMeta.label}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-(--muted-text)">
                  请选择资源查看详情。
                </div>
              )}
            </GlassPanel>
          </section>
        </div>
      </main>
    </AppSurface>
  );
}
