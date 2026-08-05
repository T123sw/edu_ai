import { useEffect, useMemo, useState } from "react";
import { backendCourseToSummary, listCourses } from "../api/courses";
import type { BackendCourse } from "../api/types";
import { buildTeacherCourseHash } from "../teacherRoutes";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  defaultCourse,
  routeHref,
  routes,
  useAppShell,
  type CourseSummary,
} from "../shared";

function CourseActions({ course, onSelect }: { course: CourseSummary; onSelect: (course: CourseSummary) => void }) {
  return (
    <div className="flex flex-wrap gap-3">
      <a
        href={buildTeacherCourseHash(routes.ai, course.id)}
        onClick={() => onSelect(course)}
        className="inline-flex items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm font-bold text-(--accent-strong) transition hover:-translate-y-px"
      >
        进入问答工作台
        <MaterialIcon name="arrow_forward" className="text-base" />
      </a>
      <a
        href={buildTeacherCourseHash(routes.resources, course.id)}
        onClick={() => onSelect(course)}
        className="inline-flex items-center gap-3 rounded-2xl border border-white/25 bg-white/10 px-5 py-4 text-sm font-bold text-white transition hover:-translate-y-px"
      >
        查看课程资源
        <MaterialIcon name="folder_open" className="text-base" />
      </a>
      <a
        href={buildTeacherCourseHash(routes.classroomStudio, course.id)}
        onClick={() => onSelect(course)}
        className="inline-flex items-center gap-3 rounded-2xl border border-white/25 bg-white/10 px-5 py-4 text-sm font-bold text-white transition hover:-translate-y-px"
      >
        AI 生成课件
        <MaterialIcon name="auto_awesome" className="text-base" />
      </a>
      <a
        href={buildTeacherCourseHash(routes.edit, course.id)}
        onClick={() => onSelect(course)}
        className="inline-flex items-center gap-3 rounded-2xl border border-white/20 bg-slate-950/16 px-5 py-4 text-sm font-bold text-white transition hover:-translate-y-px"
      >
        课程设置
        <MaterialIcon name="settings" className="text-base" />
      </a>
    </div>
  );
}

function useCourseSummaries() {
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

  const summaries = useMemo(() => courses.map((course, index) => backendCourseToSummary(course, index)), [courses]);

  return { summaries, loading, error };
}

function resolveActiveCourse(summaries: CourseSummary[], selectedCourse: CourseSummary | null) {
  return summaries.find((course) => course.id === selectedCourse?.id) ?? summaries[0] ?? selectedCourse ?? defaultCourse;
}

export function CourseListPage() {
  const { selectedCourse, setSelectedCourse } = useAppShell();
  const { summaries, loading, error } = useCourseSummaries();
  const activeCourse = resolveActiveCourse(summaries, selectedCourse);

  function openDetail(course: CourseSummary) {
    setSelectedCourse(course);
    window.location.hash = routeHref(routes.courseDetail);
  }

  return (
    <AppSurface className="min-h-screen">
      <main className="w-full px-8 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <SidebarBackLink />
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">我的课程</p>
            <p className="mt-1 text-sm text-(--muted-text)">这里只显示课程列表，点击课程后进入课程详情页。</p>
          </div>
        </div>

        {loading ? (
          <GlassPanel className="w-full border border-(--shell-border) bg-white/85 p-8 text-sm text-(--muted-text)">
            正在加载课程列表...
          </GlassPanel>
        ) : error ? (
          <GlassPanel className="w-full border border-(--shell-border) bg-white/85 p-8 text-sm text-rose-600">
            {error}
          </GlassPanel>
        ) : (
          <div className="w-full">
            <GlassPanel className="border border-(--shell-border) bg-white/88 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">课程清单</p>
                  <h2 className="mt-2 text-2xl font-black text-(--accent-strong)">全部课程</h2>
                </div>
                <div className="rounded-full bg-(--accent-soft) px-3 py-1 text-xs font-semibold text-(--accent-strong)">
                  {summaries.length} 门
                </div>
              </div>

              <div className="space-y-3">
                {summaries.map((course) => {
                  const active = course.id === activeCourse.id;
                  return (
                    <button
                      type="button"
                      onClick={() => openDetail(course)}
                      className={`w-full rounded-[22px] border p-4 text-left transition ${
                        active
                          ? "border-(--accent-border) bg-(--accent-soft) shadow-[0_16px_32px_var(--accent-shadow)]"
                          : "border-(--shell-border) bg-(--surface-subtle) hover:border-(--accent-border) hover:bg-white"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="mt-2 truncate text-base font-bold text-(--app-text)">{course.title}</h3>
                          <p className="mt-2 line-clamp-2 text-sm leading-6 text-(--muted-text)">{course.summary}</p>
                        </div>
                        <span className="rounded-full bg-white px-3 py-1 text-[10px] font-bold text-(--accent-strong)">
                          {course.progress}%
                        </span>
                      </div>
                      <div className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-(--accent)">
                        进入课程详情
                        <MaterialIcon name="arrow_forward" className="text-sm" />
                      </div>
                    </button>
                  );
                })}
              </div>
            </GlassPanel>
          </div>
        )}
      </main>
    </AppSurface>
  );
}

export function CourseDetailPage() {
  const { selectedCourse, setSelectedCourse } = useAppShell();
  const { summaries, loading, error } = useCourseSummaries();
  const activeCourse = resolveActiveCourse(summaries, selectedCourse);

  function handleSelect(course: CourseSummary) {
    setSelectedCourse(course);
  }

  return (
    <AppSurface className="min-h-screen">
      <main className="w-full px-8 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <a
            href={routeHref(routes.course)}
            className="inline-flex items-center gap-2 rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-semibold text-(--accent-strong)"
          >
            <MaterialIcon name="arrow_back" className="text-sm" />
            返回我的课程
          </a>
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">课程详情</p>
          </div>
        </div>

        {loading ? (
          <GlassPanel className="border border-(--shell-border) bg-white/85 p-8 text-sm text-(--muted-text)">
            正在加载课程详情...
          </GlassPanel>
        ) : error ? (
          <GlassPanel className="border border-(--shell-border) bg-white/85 p-8 text-sm text-rose-600">
            {error}
          </GlassPanel>
        ) : (
          <GlassPanel className="overflow-hidden border border-(--shell-border) bg-white/85">
            <div className="grid min-h-[720px] gap-0 lg:grid-cols-[0.95fr_1.25fr]">
              <section className="flex flex-col justify-between bg-[linear-gradient(160deg,var(--accent-strong),var(--accent))] p-10 text-white lg:p-14">
                <div>
                  <h1 className="mt-5 max-w-md text-5xl font-black leading-[0.95] tracking-tighter lg:text-6xl">
                    {activeCourse.uppercaseTitle}
                  </h1>
                  <p className="mt-8 max-w-md text-base leading-7 text-white/82">{activeCourse.summary}</p>
                </div>

                <div className="space-y-5">
                  
                 
                  <CourseActions course={activeCourse} onSelect={handleSelect} />
                </div>
              </section>

              <section className="relative min-h-[360px] overflow-hidden bg-slate-100">
                <img alt={activeCourse.title} className="h-full w-full object-cover" src={activeCourse.image} />
                <div className="absolute inset-x-0 bottom-0 bg-linear-to-t from-slate-950/70 via-slate-950/14 to-transparent p-8 text-white">
                  <div className="inline-flex items-center gap-2 rounded-full bg-white/14 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em]">
                 
                  </div>
                  <h2 className="mt-4 text-3xl font-black">{activeCourse.title}</h2>
                </div>
              </section>
            </div>
          </GlassPanel>
        )}
      </main>
    </AppSurface>
  );
}
