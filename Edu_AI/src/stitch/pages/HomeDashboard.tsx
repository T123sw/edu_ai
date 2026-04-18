import { useEffect, useMemo, useState } from "react";
import { backendCourseToSummary, listCourses } from "../api/courses";
import type { BackendCourse } from "../api/types";
import { AppSurface, Badge, GlassPanel, MaterialIcon, ProgressBar, routeHref, routes, useAppShell, type CourseSummary } from "../shared";

const exploreCourses = [
  { title: "教学博客生成", author: "Blog Agent", type: "生成式", price: "已接入", rating: "API" },
  { title: "知识图谱编辑", author: "Knowledge Graph", type: "课程工具", price: "已接入", rating: "API" },
  { title: "视频语义检索", author: "Video Search", type: "学习助手", price: "已接入", rating: "API" },
];

const staticProfile = {
  username: "林知夏",
  role: "课程主理人",
  email: "lin.zhixia@edu-ai.local",
};

export function HomeDashboardPage() {
  const { setSelectedCourse } = useAppShell();
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await listCourses();
        if (!cancelled) {
          setCourses(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "课程列表加载失败");
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
  }, []);

  const continueLearning = useMemo(() => courses.map(backendCourseToSummary), [courses]);

  function openCourse(course: CourseSummary) {
    setSelectedCourse(course);
    window.location.hash = routeHref(routes.course);
  }

  return (
    <AppSurface>
      <nav className="fixed left-0 right-0 top-0 z-50 flex h-16 items-center justify-between border-b border-[var(--shell-border)] bg-[var(--shell-surface)] px-8 backdrop-blur-xl">
        <div className="text-2xl font-black text-[var(--accent-strong)]">Edu AI</div>
        <div className="hidden items-center gap-8 md:flex">
          <a href={routeHref(routes.home)} className="border-b-2 border-[var(--accent)] pb-1 font-bold text-[var(--accent)]">
            首页
          </a>
          <a href={routeHref(routes.course)} className="font-medium text-[var(--muted-text)]">
            我的课程
          </a>
        </div>
        <div className="flex items-center gap-6">
          <div className="relative hidden lg:block">
            <MaterialIcon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-text)]" />
            <input className="w-64 rounded-full bg-[#e7e8e9] py-2 pl-10 pr-4 text-sm text-slate-900 outline-none" placeholder="搜索课程..." />
          </div>
          <div className="flex items-center gap-4">
            <button className="text-[var(--muted-text)]">
              <MaterialIcon name="notifications" />
            </button>
            <button className="text-[var(--muted-text)]">
              <MaterialIcon name="manage_accounts" />
            </button>
            <a
              href={routeHref(routes.profile)}
              className="flex items-center gap-3 rounded-full border border-[#163a80] bg-[linear-gradient(135deg,#163a80_0%,#2357b8_100%)] px-2 py-2 text-white shadow-[0_14px_28px_rgba(22,58,128,0.28)] transition hover:-translate-y-px"
            >
              <div className="grid h-10 w-10 place-items-center rounded-full border-2 border-white/35 bg-gradient-to-br from-[#f8fbff] via-[#dbeafe] to-[#93c5fd] text-sm font-black text-[#163a80]">
                LX
              </div>
              <div className="hidden pr-2 sm:block">
                <div className="text-sm font-bold leading-none text-white">{staticProfile.username}</div>
                <div className="mt-1 text-[11px] leading-none text-white/78">{staticProfile.role}</div>
              </div>
            </a>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-[1600px] px-8 pb-20 pt-24">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          <div className="flex flex-col gap-12 lg:col-span-9">
            <section className="overflow-hidden rounded-[28px] bg-[linear-gradient(135deg,var(--accent-strong),var(--accent))] p-8 text-white md:p-12">
              <h1 className="mb-4 text-4xl font-extrabold tracking-tight md:text-5xl">教师工作台</h1>
              <p className="mb-8 max-w-xl text-lg opacity-90">
                当前首页已改为读取后端课程列表。进入课程后，可以继续访问问答、资源、知识库、知识图谱和视频检索页面。
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl bg-white/10 p-4 backdrop-blur-md">
                  <p className="mb-1 text-xs uppercase tracking-widest opacity-70">课程总数</p>
                  <p className="text-2xl font-bold">{courses.length}</p>
                  <ProgressBar value={Math.min(100, courses.length * 12)} className="mt-3 bg-white/20" barClassName="bg-[#a3f69c]" />
                </div>
                <div className="rounded-2xl bg-white/10 p-4 backdrop-blur-md">
                  <p className="mb-1 text-xs uppercase tracking-widest opacity-70">已接能力</p>
                  <p className="text-2xl font-bold">5 项</p>
                  <p className="text-xs text-[#a3f69c]">课程 / 资源 / 知识库 / 图谱 / 视频</p>
                </div>
                <div className="rounded-2xl bg-white/10 p-4 backdrop-blur-md">
                  <p className="mb-1 text-xs uppercase tracking-widest opacity-70">问答状态</p>
                  <p className="text-2xl font-bold">在线</p>
                  <p className="text-xs text-[#a3f69c]">chat v2 已连通</p>
                </div>
              </div>
            </section>

            <section>
              <div className="mb-6 flex items-end justify-between">
                <h2 className="text-2xl font-bold">课程列表</h2>
                <a href={routeHref(routes.course)} className="flex items-center gap-1 font-semibold text-[var(--accent)]">
                  查看详情
                  <MaterialIcon name="arrow_forward" className="text-sm" />
                </a>
              </div>
              {loading ? (
                <GlassPanel className="bg-white p-8 text-sm text-[var(--muted-text)]">正在加载课程...</GlassPanel>
              ) : error ? (
                <GlassPanel className="bg-white p-8 text-sm text-rose-600">{error}</GlassPanel>
              ) : (
                <div className="flex gap-6 overflow-x-auto pb-4">
                  {continueLearning.map((course) => (
                    <button
                      key={course.id}
                      onClick={() => openCourse(course)}
                      type="button"
                      className="w-80 flex-none text-left transition hover:-translate-y-1"
                    >
                      <GlassPanel className="overflow-hidden bg-white">
                        <div className={`group h-44 bg-gradient-to-br ${course.accent}`}>
                          <div className="flex h-full items-end justify-between p-5 text-white">
                            <div>
                              <p className="text-xs uppercase tracking-[0.24em] text-white/70">{course.module}</p>
                              <h3 className="mt-2 text-2xl font-black leading-tight">{course.uppercaseTitle}</h3>
                            </div>
                            <div className="rounded-full bg-white/16 p-3 backdrop-blur-sm">
                              <MaterialIcon name="arrow_forward" />
                            </div>
                          </div>
                        </div>
                        <div className="relative p-6 pb-8">
                          <h4 className="mb-1 text-lg font-bold leading-tight">{course.title}</h4>
                          <p className="text-sm text-[#424654]">{course.instructor}</p>
                          <p className="mt-3 line-clamp-2 text-sm text-[var(--muted-text)]">{course.summary}</p>
                          <div className="mt-4 flex items-center justify-between">
                            <span className="text-xs font-semibold text-[var(--accent)]">进入课程工作区</span>
                            <span className="text-xs text-[var(--muted-text)]">{course.progress}%</span>
                          </div>
                          <div className="absolute bottom-0 left-0 h-1 rounded-br-[24px] bg-[var(--accent)]" style={{ width: `${course.progress}%` }} />
                        </div>
                      </GlassPanel>
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section>
              <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <h2 className="text-2xl font-bold">已拼接的后端能力</h2>
              </div>
              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
                {exploreCourses.map((course) => (
                  <GlassPanel key={course.title} className="bg-[#f3f4f5] p-4">
                    <div className="relative mb-4 aspect-video overflow-hidden rounded-2xl bg-[linear-gradient(135deg,#cbd5e1,#60a5fa)]" />
                    <h4 className="mb-1 font-bold">{course.title}</h4>
                    <p className="mb-3 text-sm text-[#424654]">{course.author}</p>
                    <div className="flex items-center justify-between">
                      <Badge className="bg-[var(--accent-soft)] text-[var(--accent-strong)] normal-case tracking-normal">{course.type}</Badge>
                      <span className="font-bold text-[var(--accent)]">{course.price}</span>
                    </div>
                  </GlassPanel>
                ))}
              </div>
            </section>
          </div>

          <aside className="lg:col-span-3">
            <div className="sticky top-24 space-y-8">
              <GlassPanel className="bg-white p-6">
                <div className="mb-6 flex items-center gap-2">
                  <MaterialIcon name="campaign" className="text-[var(--accent)]" />
                  <h3 className="text-lg font-bold">当前状态</h3>
                </div>
                <div className="space-y-6">
                  {[
                    ["课程列表", loading ? "同步中" : `${courses.length} 门课程`, "读取 /api/courses"],
                    ["资源页", "已接入", "读取 /api/courses/{course_id}/materials"],
                    ["知识库", "已接入", "读取 /api/courses/{course_id}/knowledge-base/documents"],
                    ["图谱页", "已接入", "读取 /api/courses/{course_id}/knowledge-graph"],
                  ].map(([title, meta, text]) => (
                    <div key={title} className="border-l-2 border-[var(--accent-soft)] pl-4">
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--muted-text)]">{meta}</p>
                      <h4 className="mb-1 text-sm font-semibold leading-tight">{title}</h4>
                      <p className="text-xs text-[#424654]">{text}</p>
                    </div>
                  ))}
                </div>
              </GlassPanel>
            </div>
          </aside>
        </div>
      </main>
    </AppSurface>
  );
}
