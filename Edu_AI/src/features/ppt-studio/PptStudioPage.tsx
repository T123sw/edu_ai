import { routeHref, routes } from "../../app/routing";
import { AppSurface, GlassPanel, MaterialIcon } from "../../shared/ui";

export function PptStudioPage() {
  return (
    <AppSurface className="overflow-hidden">
      <header className="sticky top-0 z-50 flex h-16 items-center justify-between bg-white/80 px-6 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <span className="text-xl font-extrabold tracking-tight">学术 AI</span>
          <div className="h-6 w-px bg-[#c3c6d6]" />
          <nav className="flex items-center gap-6">
            <a href={routeHref(routes.ppt)} className="border-b-2 border-[#0040a1] font-medium text-[#0040a1]">
              高等量子力学 - 第 5 页
            </a>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <button className="rounded-md px-4 py-1.5 text-sm text-[#424654]">导出</button>
          <button className="rounded-md bg-[#0040a1] px-4 py-1.5 text-sm text-white">分享</button>
          <button className="rounded-full p-2 text-[#424654]"><MaterialIcon name="more_vert" /></button>
        </div>
      </header>

      <main className="flex h-[calc(100vh-4rem)] w-full overflow-hidden">
        <section className="relative flex h-full w-[70%] flex-col bg-[#f3f4f5] p-8">
          <div className="flex h-full w-full flex-col">
            <GlassPanel className="group flex flex-1 flex-col overflow-hidden bg-white">
              <div className="flex flex-1 flex-col p-12">
                <div className="mb-8 flex items-start justify-between">
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-widest text-[#0040a1]/60">第 04 讲 - 波粒二象性</span>
                    <h1 className="mt-2 text-4xl font-extrabold">量子叠加</h1>
                  </div>
                  <div className="rounded-full bg-[#1b6d24]/10 px-3 py-1">
                    <span className="text-xs font-bold text-[#1b6d24]">核心概念</span>
                  </div>
                </div>
                <div className="grid flex-1 grid-cols-12 gap-12">
                  <div className="col-span-7 flex flex-col justify-center space-y-6">
                    <p className="text-xl leading-relaxed text-[#424654]">
                      叠加原理是量子力学的基础之一。它指出，一个物理系统，例如电子，可以同时以一定权重存在于多个理论上可能的状态中。
                    </p>
                    <ul className="space-y-4">
                      {[
                        "态矢量 |ψ⟩ 可以写成一组基态的线性组合。",
                        "测量会使波函数坍缩到某个确定的本征态。",
                        "概率由玻恩规则给出：P(x) = |ψ(x)|²。",
                      ].map((item) => (
                        <li key={item} className="flex items-start gap-3">
                          <div className="mt-1.5 h-2 w-2 rounded-full bg-[#0040a1]" />
                          <span className="font-medium text-[#424654]">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="col-span-5 flex items-center justify-center">
                    <div className="relative aspect-square w-full overflow-hidden rounded-[24px] bg-[#0040a1]/5 p-4">
                      <div className="h-full w-full rounded-2xl bg-[radial-gradient(circle_at_35%_30%,rgba(59,130,246,0.5),transparent_25%),radial-gradient(circle_at_65%_60%,rgba(79,70,229,0.45),transparent_28%),linear-gradient(135deg,rgba(59,130,246,0.25),rgba(255,255,255,0.7))]" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="rounded-2xl border border-[#c3c6d6]/20 bg-white/90 p-4 shadow-lg">
                          <code className="text-lg font-bold text-[#0040a1]">|ψ⟩ = α|0⟩ + β|1⟩</code>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="h-1.5 w-full bg-[#e1e3e4]">
                <div className="h-full w-1/3 rounded-r-full bg-[#1b6d24]" />
              </div>
            </GlassPanel>

            <div className="mt-6 flex items-center justify-between">
              <div className="flex gap-2">
                <button className="rounded-full p-2 hover:bg-white/60"><MaterialIcon name="chevron_left" /></button>
                <div className="flex items-center px-4 text-sm font-medium text-[#424654]">第 5 页 / 共 18 页</div>
                <button className="rounded-full p-2 hover:bg-white/60"><MaterialIcon name="chevron_right" /></button>
              </div>
              <div className="flex gap-4">
                <button className="flex items-center gap-2 rounded-2xl bg-white/50 px-4 py-2 text-sm font-medium">
                  <MaterialIcon name="zoom_in" className="text-sm" />
                  适应宽度
                </button>
                <button className="rounded-full bg-white/50 p-2"><MaterialIcon name="fullscreen" /></button>
              </div>
            </div>
          </div>
          <button className="absolute right-0 top-1/2 z-10 grid h-8 w-8 translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-[#c3c6d6]/20 bg-white shadow-md">
            <MaterialIcon name="last_page" className="text-sm text-[#0040a1]" />
          </button>
        </section>

        <aside className="flex h-full w-[30%] flex-col border-l border-[#c3c6d6]/10 bg-[#f8f9fa]/70 backdrop-blur-2xl">
          <div className="flex items-center justify-between border-b border-[#c3c6d6]/10 p-6">
            <div className="flex items-center gap-3">
              <div className="grid h-8 w-8 place-items-center rounded-xl bg-[#0056d2] text-white">
                <MaterialIcon name="auto_awesome" fill className="text-lg" />
              </div>
              <div>
                <h2 className="font-bold">学术助手</h2>
                <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[#1b6d24]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#1b6d24]" />
                  量子专家已启用
                </span>
              </div>
            </div>
            <button className="rounded-full p-2"><MaterialIcon name="close_fullscreen" /></button>
          </div>

          <div className="flex-1 space-y-8 overflow-y-auto p-6">
            <div className="space-y-2">
              <div className="rounded-2xl rounded-tl-none bg-[#e7e8e9]/50 p-4">
                <p className="text-sm leading-relaxed text-[#424654]">
                  你好，我会帮助你理解量子力学中的复杂概念。我们当前正在查看<strong className="text-[#0040a1]">第 5 页：量子叠加</strong>。你想深入了解狄拉克符号，还是玻恩规则？
                </p>
              </div>
              <span className="px-1 text-[10px] text-[#737785]">刚刚</span>
            </div>

            <div className="text-right">
              <div className="inline-block rounded-2xl rounded-tr-none bg-[#0040a1] p-4 text-left text-sm leading-relaxed text-white">
                能解释一下图中的数学关系吗？尤其是 α 和 β 分别代表什么？
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl rounded-tl-none border border-[#c3c6d6]/10 bg-white p-5 shadow-sm">
                <p className="mb-4 text-sm leading-relaxed text-[#424654]">
                  在态矢量方程 <code className="rounded bg-[#e7e8e9] px-1 text-[#0040a1]">|ψ⟩ = α|0⟩ + β|1⟩</code> 中：
                </p>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <MaterialIcon name="check_circle" className="mt-0.5 text-sm text-[#1b6d24]" />
                    <p className="text-sm text-[#424654]"><strong>概率振幅：</strong>α 和 β 是复数，分别表示系统处于 |0⟩ 与 |1⟩ 状态的振幅。</p>
                  </li>
                  <li className="flex items-start gap-3">
                    <MaterialIcon name="check_circle" className="mt-0.5 text-sm text-[#1b6d24]" />
                    <p className="text-sm text-[#424654]"><strong>归一化条件：</strong>为了满足物理意义，模方之和必须等于 1：<code className="text-[#0040a1]">|α|² + |β|² = 1</code>。</p>
                  </li>
                </ul>
                <div className="mt-4 flex items-center gap-2 border-t border-[#c3c6d6]/10 pt-4">
                  <MaterialIcon name="lightbulb" className="text-sm text-[#0040a1]" />
                  <span className="text-xs font-medium text-[#0040a1]">可以把 |α|² 理解为粒子被测得处于 |0⟩ 状态的概率。</span>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="rounded-full border border-[#c3c6d6]/30 px-3 py-1 text-xs text-[#424654]">查看推导</button>
                <button className="rounded-full border border-[#c3c6d6]/30 px-3 py-1 text-xs text-[#424654]">现实案例</button>
              </div>
            </div>
          </div>

          <div className="border-t border-[#c3c6d6]/10 bg-white/40 p-6 backdrop-blur-md">
            <div className="group relative">
              <div className="absolute inset-0 rounded-2xl bg-[#0040a1]/5 opacity-0 blur-xl transition-opacity group-focus-within:opacity-100" />
              <div className="relative flex items-end gap-2 rounded-2xl border border-transparent bg-[#e7e8e9]/40 p-1.5 focus-within:border-[#0040a1]/20 focus-within:bg-white">
                <textarea className="min-h-[52px] flex-1 resize-none border-none bg-transparent px-3 py-3 text-sm outline-none" placeholder="请输入你对量子叠加的疑问..." rows={1} />
                <div className="flex items-center gap-1 p-1">
                  <button className="rounded-xl p-2 text-[#737785] hover:bg-[#0040a1]/5 hover:text-[#0040a1]"><MaterialIcon name="mic" /></button>
                  <button className="rounded-xl bg-[#0040a1] p-2 text-white shadow-lg"><MaterialIcon name="send" /></button>
                </div>
              </div>
            </div>
            <p className="mt-3 text-center text-[10px] text-[#737785]">AI 可能出错，关键结论请自行核验。</p>
          </div>
        </aside>
      </main>

      <button className="fixed bottom-8 left-8 flex items-center gap-3 rounded-full border border-[#c3c6d6]/20 bg-white px-4 py-4 shadow-2xl">
        <div className="grid h-10 w-10 place-items-center rounded-full bg-[#a0f399] text-[#217128]">
          <MaterialIcon name="edit_note" />
        </div>
        <span className="pr-2 font-bold">添加学习笔记</span>
      </button>
    </AppSurface>
  );
}
