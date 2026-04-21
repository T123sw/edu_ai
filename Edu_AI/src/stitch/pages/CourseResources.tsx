import { useEffect, useMemo, useState } from "react";
import { courseMaterialToMarkdown, getCourseMaterials } from "../api/courses";
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
  routeHref,
  routes,
  useAppShell,
} from "../shared";

const typeLabels: Record<string, string> = {
  blog: "博客",
  report: "报告",
  lesson_plan: "教案",
  ppt: "PPT",
  quiz: "测验",
};

export function CourseResourcesPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getCourseMaterials(course.id);
        if (!cancelled) {
          setMaterials(data);
          setActiveId(data[0]?.material_id ?? null);
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
  }, [course.id]);

  const grouped = useMemo(() => {
    return materials.reduce<Record<string, CourseMaterial[]>>((acc, item) => {
      const key = item.material_type || "other";
      acc[key] = acc[key] || [];
      acc[key].push(item);
      return acc;
    }, {});
  }, [materials]);

  const activeMaterial = materials.find((item) => item.material_id === activeId) ?? materials[0] ?? null;
  const markdown = activeMaterial ? courseMaterialToMarkdown(activeMaterial) : "";

  return (
    <AppSurface className="flex min-h-screen xl:h-screen xl:overflow-hidden">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">{course.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">课程资源</p>
        </div>
        <SidebarNav activeRoute={routes.resources} />
        <div className="rounded-[24px] bg-[var(--accent-soft)] p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">资源概览</p>
          <div className="mt-3 space-y-2 text-sm text-[var(--accent-strong)]">
            <div className="flex items-center justify-between rounded-2xl bg-white px-4 py-3">
              <span>材料总数</span>
              <span className="font-bold">{materials.length}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-[var(--shell-border)] px-4 py-3">
              <span>当前课程</span>
              <span className="truncate pl-4 text-right">{course.id}</span>
            </div>
          </div>
        </div>
      </SidebarDock>

      <main className="flex min-h-0 flex-1 flex-col xl:overflow-hidden">
        <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">{course.module}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-[var(--accent-strong)] sm:text-4xl">课程资源中心</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--muted-text)]">
          </p>
        </header>

        <div className="grid flex-1 gap-6 p-6 xl:min-h-0 xl:grid-cols-[360px_minmax(0,1fr)] xl:overflow-hidden">
          <section className="flex min-h-0 flex-col overflow-hidden">
            {loading ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-[var(--muted-text)]">正在加载资源...</GlassPanel>
            ) : error ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-rose-600">{error}</GlassPanel>
            ) : materials.length === 0 ? (
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 text-sm text-[var(--muted-text)]">当前课程还没有生成材料。</GlassPanel>
            ) : (
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-2">
                {Object.entries(grouped).map(([type, items]) => (
                  <GlassPanel key={type} className="border border-[var(--shell-border)] bg-white/90 p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{type}</p>
                      <h3 className="mt-2 text-xl font-black text-[var(--accent-strong)]">{typeLabels[type] || type}</h3>
                    </div>
                    <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-bold text-[var(--accent-strong)]">
                      {items.length} 项
                    </span>
                  </div>
                  <div className="space-y-3">
                    {items.map((item) => {
                      const active = item.material_id === activeMaterial?.material_id;
                      return (
                        <button
                          key={item.material_id}
                          type="button"
                          onClick={() => setActiveId(item.material_id)}
                          className={`w-full rounded-[22px] border px-4 py-4 text-left transition ${
                            active
                              ? "border-[var(--accent-border)] bg-[var(--accent-soft)]"
                              : "border-[var(--shell-border)] bg-[var(--surface-subtle)] hover:border-[var(--accent-border)] hover:bg-white"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <h4 className="text-sm font-bold text-[var(--app-text)]">{item.title || item.topic || item.material_id}</h4>
                              <p className="mt-2 line-clamp-2 text-sm text-[var(--muted-text)]">{item.summary || "点击查看材料预览。"}</p>
                            </div>
                            {item.is_pinned ? (
                              <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-[var(--accent-strong)]">置顶</span>
                            ) : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  </GlassPanel>
                ))}
              </div>
            )}
          </section>

          <section className="min-h-0 min-w-0">
            <GlassPanel className="flex h-full min-h-0 flex-col border border-[var(--shell-border)] bg-white/90 p-6">
              {activeMaterial ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] pb-4">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">{activeMaterial.material_type}</p>
                      <h2 className="mt-2 text-3xl font-black text-[var(--accent-strong)]">
                        {activeMaterial.title || activeMaterial.topic || activeMaterial.material_id}
                      </h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        window.localStorage.setItem("stitch-video-lesson", "l42");
                        window.location.hash = routeHref(routes.video);
                      }}
                      className="inline-flex items-center gap-2 rounded-full bg-[var(--accent)] px-5 py-3 text-sm font-bold text-white"
                    >
                      <MaterialIcon name="play_circle" className="text-base" />
                      去视频页
                    </button>
                  </div>
                  <div className="mt-6 min-h-0 flex-1 overflow-y-auto pr-2">
                    <MarkdownPreview content={markdown} />
                  </div>
                </>
              ) : (
                <div className="text-sm text-[var(--muted-text)]">请选择左侧资源查看预览。</div>
              )}
            </GlassPanel>
          </section>
        </div>
      </main>
    </AppSurface>
  );
}
