import { AppSurface, GlassPanel, MaterialIcon, SidebarBackLink, SidebarDock, SidebarNav, defaultCourse, routes, useAppShell } from "../shared";

const milestones = [
  { title: "第一单元：偏导与梯度", status: "已完成", icon: "check_circle", tone: "bg-emerald-100 text-emerald-700" },
  { title: "第二单元：多重积分", status: "进行中", icon: "pending", tone: "bg-blue-100 text-blue-700" },
] as const;

export function CourseEditPage() {
  const { selectedCourse } = useAppShell();
  const course = selectedCourse ?? defaultCourse;

  return (
    <AppSurface className="flex min-h-screen">
      <SidebarDock className="h-screen gap-3 bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)] p-4">
        <div className="mb-2 px-2 py-4">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">{course.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">详情编辑</p>
        </div>

        <SidebarNav activeRoute={routes.edit} />
      </SidebarDock>

      <main className="flex flex-1 flex-col xl:flex-row">
        <div className="flex-1 p-6 sm:p-8">
          <div className="mx-auto max-w-4xl">
            <header className="mb-10">
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--accent-strong)]">{course.module}</p>
              <h1 className="mt-2 text-4xl font-black tracking-tight text-[var(--accent-strong)]">编辑课程详情页</h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--muted-text)]">基于主页点击后的课程详情展示信息进行编辑，布局参考你提供的 `detail/edit.html`。</p>
            </header>

            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-6 sm:p-8">
              <form className="space-y-8">
                <div>
                  <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">课程标题</label>
                  <input className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-sm outline-none" defaultValue={course.title} />
                </div>

                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">模块编号</label>
                    <div className="relative">
                      <input className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-sm outline-none" defaultValue={course.module} />
                      <MaterialIcon name="layers" className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                  </div>
                  <div>
                    <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">预计学时</label>
                    <div className="relative">
                      <input className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-sm outline-none" defaultValue="45 学时" />
                      <MaterialIcon name="schedule" className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">课程摘要</label>
                  <textarea className="min-h-[180px] w-full rounded-[24px] bg-slate-50 px-4 py-4 text-sm leading-7 outline-none" defaultValue={course.summary} />
                </div>

                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">讲师名称</label>
                    <input className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-sm outline-none" defaultValue={course.instructor} />
                  </div>
                  <div>
                    <label className="mb-3 block text-sm font-semibold text-[var(--app-text)]">课程封面地址</label>
                    <input className="w-full rounded-2xl bg-slate-50 px-4 py-3 text-sm outline-none" defaultValue={course.image} />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-4 pt-4">
                  <button className="rounded-full px-6 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100" type="button">
                    放弃修改
                  </button>
                  <button className="rounded-full bg-[var(--accent)] px-8 py-2.5 text-sm font-semibold text-white" type="submit">
                    更新详情信息
                  </button>
                </div>
              </form>
            </GlassPanel>

            <section className="mt-10">
              <h2 className="text-2xl font-black text-[var(--accent-strong)]">教学里程碑</h2>
              <div className="mt-6 space-y-4">
                {milestones.map((item) => (
                  <GlassPanel key={item.title} className="border border-[var(--shell-border)] bg-white/90 p-5">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-4">
                        <div className={`grid h-11 w-11 place-items-center rounded-2xl ${item.tone}`}>
                          <MaterialIcon name={item.icon} className="text-[20px]" />
                        </div>
                        <div>
                          <p className="font-bold text-[var(--app-text)]">{item.title}</p>
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--muted-text)]">{item.status}</p>
                        </div>
                      </div>
                      <button className="rounded-full border border-[var(--shell-border)] px-4 py-2 text-sm font-semibold text-[var(--muted-text)]">
                        编辑
                      </button>
                    </div>
                  </GlassPanel>
                ))}
              </div>
            </section>
          </div>
        </div>

        <aside className="w-full border-t border-[var(--shell-border)] bg-[var(--panel-surface)] p-6 xl:w-[360px] xl:border-l xl:border-t-0">
          <div className="space-y-6 xl:sticky xl:top-6">
            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-5">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--muted-text)]">课程封面</p>
              <div className="mt-4 overflow-hidden rounded-[24px] bg-slate-100">
                <img alt={course.title} className="aspect-video w-full object-cover" src={course.image} />
              </div>
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-[var(--muted-text)]">当前封面预览</span>
                <button className="font-bold text-[var(--accent-strong)]">替换封面</button>
              </div>
            </GlassPanel>

            <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MaterialIcon name="hub" className="text-[var(--accent)]" />
                  <span className="font-bold text-[var(--app-text)]">知识图谱同步</span>
                </div>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <div className="mt-4 space-y-3 text-sm text-[var(--muted-text)]">
                <div className="flex items-center justify-between">
                  <span>同步状态</span>
                  <span className="font-semibold text-emerald-700">已同步</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[var(--track-color)]">
                  <div className="h-full w-full rounded-full bg-emerald-500" />
                </div>
                <p>更新课程详情后，可重新索引课程节点和知识摘要。</p>
              </div>
              <button className="mt-4 w-full rounded-2xl bg-[var(--accent-soft)] px-4 py-3 text-sm font-bold text-[var(--accent-strong)]">
                重新索引节点
              </button>
            </GlassPanel>

            <div className="grid grid-cols-2 gap-3">
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-4 text-center">
                <p className="text-2xl font-black text-[var(--accent-strong)]">84%</p>
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--muted-text)]">展示完整度</p>
              </GlassPanel>
              <GlassPanel className="border border-[var(--shell-border)] bg-white/90 p-4 text-center">
                <p className="text-2xl font-black text-[var(--accent-strong)]">1.2k</p>
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--muted-text)]">引用量</p>
              </GlassPanel>
            </div>
          </div>
        </aside>
      </main>
    </AppSurface>
  );
}
