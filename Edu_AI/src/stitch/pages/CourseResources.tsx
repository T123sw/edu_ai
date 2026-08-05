import { useEffect, useMemo, useState } from "react";
import {
  courseMaterialToMarkdown,
  deleteCourseMaterial,
  getCourseMaterials,
  pinCourseMaterial,
  renameCourseMaterial,
} from "../api/courses";
import {
  COURSE_MATERIAL_FILTERS,
  getCourseMaterialOpenTarget,
  getCourseMaterialTypeMeta,
  isCourseMaterialInFilter,
  type CourseMaterialFilterKey,
} from "../api/courseMaterialPresentation";
import type { CourseMaterial } from "../api/types";
import { MarkdownPreview } from "../components/MarkdownPreview";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  defaultCourse,
  routes,
  useAppShell,
} from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";

type ResourceSort = "recent" | "title";

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
    return `${scenes} 个场景 · ${formatMaterialDate(material)}`;
  }
  return material.summary || `更新于 ${formatMaterialDate(material)}`;
}

export function CourseResourcesPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] =
    useState<CourseMaterialFilterKey>("all");
  const [query, setQuery] = useState("");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [sort, setSort] = useState<ResourceSort>("recent");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getCourseMaterials(course.id);
        if (!cancelled) {
          setMaterials(data);
          setActiveId((current) =>
            data.some((item) => item.material_id === current)
              ? current
              : (data[0]?.material_id ?? null),
          );
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
  }, [course.id, reloadToken]);

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

    return [...filtered].sort((left, right) => {
      if (left.is_pinned !== right.is_pinned) return left.is_pinned ? -1 : 1;
      if (sort === "title") {
        return getMaterialTitle(left).localeCompare(
          getMaterialTitle(right),
          "zh-CN",
        );
      }
      return getMaterialTimestamp(right) - getMaterialTimestamp(left);
    });
  }, [activeFilter, materials, pinnedOnly, query, sort]);

  useEffect(() => {
    if (
      activeId &&
      filteredMaterials.some((material) => material.material_id === activeId)
    ) {
      return;
    }
    setActiveId(filteredMaterials[0]?.material_id ?? null);
  }, [activeId, filteredMaterials]);

  useEffect(() => {
    setEditingTitle(false);
    setActionError(null);
  }, [activeId]);

  const activeMaterial =
    filteredMaterials.find((item) => item.material_id === activeId)
    ?? filteredMaterials[0]
    ?? null;
  const markdown = activeMaterial
    ? courseMaterialToMarkdown(activeMaterial)
    : "";

  function openMaterial(material: CourseMaterial) {
    const target = getCourseMaterialOpenTarget(material);
    if (target.kind === "route") {
      window.location.hash = target.value;
      return;
    }
    setActiveId(target.value);
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
      setMaterials((current) => current.map((item) => (
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
      setMaterials((current) => current.map((item) => (
        item.material_id === updated.material_id
        && item.material_type === updated.material_type
          ? updated
          : item
      )));
      setEditingTitle(false);
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
      setMaterials((current) => current.filter((item) => !(
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
  const previewSupported =
    activeMaterial
    && activeMaterial.material_type !== "classroom"
    && activeMeta?.known;

  return (
    <AppSurface className="flex min-h-screen xl:h-screen xl:overflow-hidden">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-(--accent-strong)">
            {course.title}
          </h1>
          <p className="mt-1 text-sm text-(--muted-text)">课程资源</p>
        </div>
        <SidebarNav activeRoute={routes.resources} />
        <div className="rounded-[24px] bg-(--accent-soft) p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-(--accent-strong)">
            资源概览
          </p>
          <div className="mt-3 space-y-2 text-sm text-(--accent-strong)">
            <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3">
              <span>资源总数</span>
              <span className="font-bold">{materials.length}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-(--shell-border) px-4 py-3">
              <span>AI 课堂</span>
              <span className="font-bold">
                {
                  materials.filter(
                    (material) => material.material_type === "classroom",
                  ).length
                }
              </span>
            </div>
          </div>
        </div>
      </SidebarDock>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden xl:overflow-y-hidden">
        <header className="border-b border-(--shell-border) bg-(--app-bg)/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-(--accent-strong)">
                {course.module}
              </p>
              <h1 className="mt-1 text-3xl font-black tracking-tight text-(--accent-strong)">
                课程资源中心
              </h1>
              <p className="mt-2 text-sm text-(--muted-text)">
                AI 课堂与所有生成结果共用同一份课程资源记录。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
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
                <option value="title">按标题</option>
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

          <div
            className="mt-4 flex flex-wrap gap-2"
            role="tablist"
            aria-label="资源类型筛选"
          >
            {COURSE_MATERIAL_FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                role="tab"
                aria-selected={activeFilter === filter.key}
                onClick={() => setActiveFilter(filter.key)}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  activeFilter === filter.key
                    ? "bg-(--accent) text-white"
                    : "border border-(--shell-border) bg-white text-(--muted-text) hover:border-(--accent-border)"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </header>

        <div className="grid min-h-0 min-w-0 flex-1 gap-5 p-5 xl:grid-cols-[340px_minmax(0,1fr)] xl:overflow-hidden">
          <section className="flex min-h-0 min-w-0 flex-col overflow-hidden">
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
                <h2 className="font-bold text-(--app-text)">
                  当前课程还没有生成资源
                </h2>
                <p className="mt-2 text-sm leading-6 text-(--muted-text)">
                  可以前往问答／生成工厂创建教学资源，或进入 AI 课堂开始备课。
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <a
                    href={buildTeacherCourseHash(routes.ai, course.id)}
                    className="rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white"
                  >
                    前往生成工厂
                  </a>
                  <a
                    href={buildTeacherCourseHash(
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
                    material.material_id === activeMaterial?.material_id;
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
              {activeMaterial && activeMeta ? (
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
                        <h2 className="mt-2 truncate text-2xl font-black text-(--accent-strong)">
                          {getMaterialTitle(activeMaterial)}
                        </h2>
                      )}
                      <p className="mt-2 text-xs text-(--muted-text)">
                        {formatMaterialDate(activeMaterial)}
                        {activeMaterial.scope_id
                          ? ` · 知识点 ${activeMaterial.scope_id}`
                          : " · 课程级资源"}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
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

                  <div className="mt-5 min-h-0 min-w-0 flex-1 overflow-y-auto pr-2">
                    {activeMaterial.material_type === "classroom" ? (
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
                      <MarkdownPreview content={markdown} />
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
                              {activeMaterial.material_type || "unknown"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-(--muted-text)">资源 ID</dt>
                            <dd className="mt-1 break-all font-semibold text-(--app-text)">
                              {activeMaterial.material_id}
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
