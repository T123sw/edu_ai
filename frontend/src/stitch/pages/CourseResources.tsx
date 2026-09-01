import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import {
  backendCourseToSummary,
  deleteCourseMaterial,
  getCourseMaterial,
  getCourseMaterials,
  pinCourseMaterial,
  renameCourseMaterial,
} from "../api/courses";
import {
  getCourseMaterialFiltersForRole,
  getCourseMaterialOpenTarget,
  getCourseMaterialTypeMeta,
  isCourseMaterialInFilter,
  toCourseMaterialPresentation,
  type CourseMaterialFilterKey,
} from "../api/courseMaterialPresentation";
import {
  courseMaterialKey,
  readCourseMaterialTarget,
} from "../api/courseMaterialTarget";
import type { CourseMaterial } from "../api/types";
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
import { MaterialContentEditor } from "./MaterialContentEditor";

type ResourceSort = "recent" | "title";

const EDITABLE_MATERIAL_TYPES = new Set([
  "report",
  "blog",
  "lesson_plan",
  "quiz",
  "flashcard",
  "graph",
  "classroom",
]);

function getKeyboardSelection<T extends string>(
  key: string,
  current: T,
  choices: readonly T[],
): T | null {
  const currentIndex = Math.max(choices.indexOf(current), 0);
  if (key === "ArrowRight" || key === "ArrowDown") {
    return choices[(currentIndex + 1) % choices.length];
  }
  if (key === "ArrowLeft" || key === "ArrowUp") {
    return choices[(currentIndex - 1 + choices.length) % choices.length];
  }
  if (key === "Home") return choices[0];
  if (key === "End") return choices[choices.length - 1];
  return null;
}

function getMaterialTitle(material: CourseMaterial): string {
  return material.title || material.topic || material.material_id;
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

function getMaterialSummary(material: CourseMaterial): string {
  if (material.material_type === "classroom") {
    const scenes = material.scenes_count ?? material.scenes?.length ?? 0;
    return `${scenes} 个场景 · 更新于 ${formatMaterialDate(material)}`;
  }
  return `更新于 ${formatMaterialDate(material)}`;
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
  const [personalMaterials, setPersonalMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] =
    useState<CourseMaterialFilterKey>("all");
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
  const visibleMaterialFilters = useMemo(
    () => getCourseMaterialFiltersForRole(user?.role),
    [user?.role],
  );

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
            setActiveFilter("all");
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
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "资源加载失败");
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
      if (!isCourseMaterialInFilter(material, activeFilter)) return false;
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
  }, [activeFilter, materials, pinnedOnly, query]);

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
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "置顶操作失败");
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
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "重命名失败");
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
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "删除资源失败");
    } finally {
      setActionBusy(false);
    }
  }

  const activeMeta = activeMaterial
    ? getCourseMaterialTypeMeta(activeMaterial.material_type)
    : null;
  const activePresentation = activeMaterial
    ? toCourseMaterialPresentation(activeMaterial)
    : null;

  function handleFilterKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    current: CourseMaterialFilterKey,
  ) {
    const next = getKeyboardSelection(
      event.key,
      current,
      visibleMaterialFilters.map((filter) => filter.key),
    );
    if (!next) return;
    event.preventDefault();
    setActiveFilter(next);
    window.requestAnimationFrame(() => {
      document.getElementById(`resource-filter-${next}`)?.focus();
    });
  }
  const previewSupported =
    activeMaterial
    && activeMaterial.material_type !== "classroom"
    && activeMeta?.known;

  return (
    <AppSurface className="flex min-h-[calc(100vh-var(--course-header-height))] min-[1180px]:h-[calc(100vh-var(--course-header-height))] min-[1180px]:overflow-hidden">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden min-[1180px]:overflow-y-hidden">
        <header className="border-b border-(--shell-border) bg-(--app-bg)/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <div className="flex min-w-0 flex-nowrap items-center gap-3 overflow-hidden">
            <div
              className="resource-type-filter flex min-w-0 flex-1 flex-nowrap gap-2 overflow-x-auto"
              role="radiogroup"
              aria-label="资源类型筛选"
            >
              {visibleMaterialFilters.map((filter) => (
                <button
                  key={filter.key}
                  id={`resource-filter-${filter.key}`}
                  type="button"
                  role="radio"
                  aria-checked={activeFilter === filter.key}
                  tabIndex={activeFilter === filter.key ? 0 : -1}
                  onClick={() => setActiveFilter(filter.key)}
                  onKeyDown={(event) => handleFilterKeyDown(event, filter.key)}
                  className={`shrink-0 whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
                    activeFilter === filter.key
                      ? "bg-(--accent) text-white"
                      : "border border-(--shell-border) bg-white text-(--muted-text) hover:border-(--accent-border)"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>
            <div className="flex shrink-0 flex-nowrap items-center justify-end gap-2">
              <label className="relative">
                <MaterialIcon
                  name="search"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-base text-(--muted-text)"
                />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索资源"
                  className="h-10 w-52 rounded-full border border-(--shell-border) bg-white pl-10 pr-4 text-sm outline-hidden focus:border-(--accent-border)"
                />
              </label>
              <select
                aria-label="资源排序"
                value={sort}
                onChange={(event) => setSort(event.target.value as ResourceSort)}
                className="h-10 rounded-full border border-(--shell-border) bg-white px-4 text-sm text-(--app-text)"
              >
                <option value="recent">最近更新</option>
                <option value="title">按名称</option>
              </select>
              <label className="inline-flex h-10 items-center gap-2 rounded-full border border-(--shell-border) bg-white px-4 text-sm text-(--app-text)">
                <input
                  type="checkbox"
                  checked={pinnedOnly}
                  onChange={(event) => setPinnedOnly(event.target.checked)}
                />
                仅看置顶
              </label>
            </div>
          </div>
        </header>

        <div className="grid min-h-0 min-w-0 flex-1 gap-5 p-5 min-[1180px]:grid-cols-[340px_minmax(0,1fr)] min-[1180px]:overflow-hidden">
          <section className="flex max-h-[360px] min-h-0 min-w-0 flex-col overflow-hidden min-[1180px]:max-h-none">
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
                  可以前往问答／生成工厂创建内容，生成后默认仅自己可见。
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <a
                    href={buildRoleCourseHash(user?.role, routes.ai, course.id)}
                    className="rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white"
                  >
                    前往生成工厂
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
              <div className="min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto pr-2">
                {filteredMaterials.map((material) => {
                  const meta = getCourseMaterialTypeMeta(
                    material.material_type,
                  );
                  const active =
                    courseMaterialKey(
                      material.material_type,
                      material.material_id,
                    ) === activeKey;
                  return (
                    <button
                      key={`${material.material_type}:${material.material_id}`}
                      type="button"
                      onClick={() => openMaterial(material)}
                      className={`w-full rounded-[22px] border p-4 text-left transition ${
                        active
                          ? "border-(--accent-border) bg-(--accent-soft)"
                          : "border-(--shell-border) bg-white/90 hover:border-(--accent-border) hover:bg-white"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-(--surface-subtle) text-(--accent-strong)">
                          <MaterialIcon name={meta.icon} className="text-xl" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            <span className="text-xs font-bold text-(--accent-strong)">
                              {meta.label}
                            </span>
                            {material.is_pinned ? (
                              <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold text-(--accent-strong)">
                                置顶
                              </span>
                            ) : null}
                          </span>
                          <span className="mt-1 block truncate text-sm font-bold text-(--app-text)">
                            {getMaterialTitle(material)}
                          </span>
                          <span className="mt-1 block line-clamp-2 text-xs leading-5 text-(--muted-text)">
                            {getMaterialSummary(material)}
                          </span>
                        </span>
                        <MaterialIcon
                          name={
                            material.material_type === "classroom"
                              ? "play_circle"
                              : "chevron_right"
                          }
                          className="mt-1 shrink-0 text-xl text-(--accent)"
                        />
                      </div>
                    </button>
                  );
                })}
              </div>
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
                      无法恢复任务结果
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
                      <span className="mt-2 inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">
                        {activePresentation?.statusLabel}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
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

                  {activePresentation ? (
                    <dl className="resource-factual-meta">
                      {activePresentation.meta.filter((item) => item.label !== "可见范围").map((item) => (
                        <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
                      ))}
                    </dl>
                  ) : null}

                  <div className="mt-5 min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden pr-2">
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
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-2xl bg-(--surface-subtle) p-5">
                          <p className="text-xs font-semibold text-(--muted-text)">
                            场景数量
                          </p>
                          <p className="mt-2 text-2xl font-black text-(--accent-strong)">
                            {activeMaterial.scenes_count
                              ?? activeMaterial.scenes?.length
                              ?? 0}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-(--surface-subtle) p-5">
                          <p className="text-xs font-semibold text-(--muted-text)">
                            语音状态
                          </p>
                          <p className="mt-2 font-bold text-(--app-text)">
                            {activeMaterial.voice_status || "跟随课堂场景"}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-(--surface-subtle) p-5">
                          <p className="text-xs font-semibold text-(--muted-text)">
                            最近视频导出
                          </p>
                          <p className="mt-2 font-bold text-(--app-text)">
                            {activeMaterial.video_status || "尚未导出"}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-(--surface-subtle) p-5">
                          <p className="text-xs font-semibold text-(--muted-text)">
                            来源资料
                          </p>
                          <p className="mt-2 font-bold text-(--app-text)">
                            {activeMaterial.source_count ?? "未记录"}
                          </p>
                        </div>
                      </div>
                    ) : previewSupported ? (
                      <CourseMaterialArtifactPreview material={activeMaterial} />
                    ) : (
                      <div className="rounded-2xl border border-dashed border-(--shell-border) bg-(--surface-subtle) p-6">
                        <h3 className="font-bold text-(--app-text)">
                          暂无专用预览
                        </h3>
                        <p className="mt-2 text-sm leading-6 text-(--muted-text)">
                          此资源类型仍保留在总列表中，但系统不会将它错误地跳转到视频页或其他预览器。
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
