import { AppSurface, GlassPanel, MaterialIcon, SidebarBackLink, defaultCourse, routeHref, routes, useAppShell } from "../shared";

export function CourseDetailPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;

  return (
    <AppSurface className="min-h-screen">
      <main className="mx-auto max-w-[1500px] px-8 py-10">
        <div className="mb-8">
          <SidebarBackLink />
        </div>

        <GlassPanel className="overflow-hidden border border-[var(--shell-border)] bg-white/85">
          <div className="grid min-h-[640px] gap-0 lg:grid-cols-[0.95fr_1.25fr]">
            <section className="flex flex-col justify-between bg-[linear-gradient(160deg,var(--accent-strong),var(--accent))] p-10 text-white lg:p-14">
              <div>
                <p className="mb-4 text-xs font-bold uppercase tracking-[0.36em] text-white/70">{course.module}</p>
                <h1 className="max-w-md text-5xl font-black leading-[0.95] tracking-[-0.05em] lg:text-6xl">
                  {course.uppercaseTitle}
                </h1>
                <p className="mt-8 max-w-md text-base leading-7 text-white/82">{course.summary}</p>
              </div>

              <div className="space-y-5">
                <div className="flex items-center gap-3 text-sm text-white/80">
                  <MaterialIcon name="school" className="text-xl" />
                  <span>课程详情展示页</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-white/80">
                  <MaterialIcon name="auto_graph" className="text-xl" />
                  <span>课程信息与工作台入口已就绪</span>
                </div>
                <div className="flex flex-wrap gap-3">
                  <a
                    href={routeHref(routes.workspace)}
                    className="inline-flex items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm font-bold text-[var(--accent-strong)] transition hover:-translate-y-px"
                  >
                    进入问答工作台
                    <MaterialIcon name="arrow_forward" className="text-base" />
                  </a>
                  <a
                    href={routeHref(routes.resources)}
                    className="inline-flex items-center gap-3 rounded-2xl border border-white/25 bg-white/10 px-5 py-4 text-sm font-bold text-white transition hover:-translate-y-px"
                  >
                    打开课程资源
                    <MaterialIcon name="description" className="text-base" />
                  </a>
                </div>
              </div>
            </section>

            <section className="relative min-h-[360px] overflow-hidden bg-slate-100">
              <img alt={course.title} className="h-full w-full object-cover" src={course.image} />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/65 via-slate-950/10 to-transparent p-8 text-white">
                <div className="inline-flex items-center gap-2 rounded-full bg-white/14 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em]">
                  <MaterialIcon name="hub" className="text-sm" />
                  Course Overview
                </div>
                <p className="mt-4 max-w-lg text-sm leading-6 text-white/88">
                  右侧区域保持最初版本的课程视觉封面，用于承接课程图像、概览氛围和课程入口说明。
                </p>
              </div>
            </section>
          </div>
        </GlassPanel>
      </main>
    </AppSurface>
  );
}
