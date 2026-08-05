import { AppSurface, GlassPanel, MaterialIcon, routeHref, routes, useAppShell } from "../shared";

const profile = {
  username: "林知夏",
  role: "课程主理人 / 教学设计师",
  email: "lin.zhixia@edu-ai.local",
  phone: "+86 138 0000 1024",
  department: "课程研发中心",
  bio: "负责课程结构设计、知识图谱维护与教师问答工作流配置。当前个人主页以静态展示为主，用于集中展示账号信息、安全设置和常用入口。",
};

const accountFields = [
  ["用户名", profile.username],
  ["邮箱", profile.email],
  ["手机号", profile.phone],
  ["所属部门", profile.department],
];

const securityItems = [
  ["登录密码", "上次更新于 2025-02-18"],
  ["账号状态", "正常，可访问全部教师页面"],
  ["头像设置", "当前使用静态默认头像"],
];

const quickLinks = [
  { title: "AI 服务配置", subtitle: "配置模型、语音、搜索与解析服务", href: routeHref(routes.settings), icon: "settings_suggest" },
  { title: "我的课程", subtitle: "继续查看课程与工作区", href: routeHref(routes.course), icon: "dashboard" },
  { title: "问答助手", subtitle: "进入教师 AI 工作台", href: routeHref(routes.ai), icon: "forum" },
  { title: "知识图谱", subtitle: "维护节点与课程关系", href: routeHref(routes.graph), icon: "hub" },
];

export function ProfilePage() {
  const { logout } = useAppShell();

  return (
    <AppSurface className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(191,219,254,0.72),transparent_24%),radial-gradient(circle_at_top_right,rgba(147,197,253,0.22),transparent_18%),linear-gradient(180deg,#f4f8ff_0%,#e7eefc_100%)]">
      <main className="w-full px-8 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <a
            href={routeHref(routes.home)}
            className="inline-flex items-center gap-2 rounded-full border border-[#c6d4ef] bg-white px-4 py-2 text-sm font-semibold text-[#17304a] shadow-[0_10px_24px_rgba(15,23,42,0.08)]"
          >
            <MaterialIcon name="arrow_back" className="text-base" />
            返回首页
          </a>
          <div className="rounded-full border border-[#c7d8ff] bg-[#eef4ff] px-4 py-2 text-xs font-bold uppercase tracking-[0.24em] text-[#163a80]">
            Personal Home
          </div>
        </div>

        <section className="overflow-hidden rounded-[34px] border border-[#d4ddf3] bg-[linear-gradient(135deg,#0f172a_0%,#163a80_46%,#2563eb_100%)] text-white shadow-[0_28px_72px_rgba(15,23,42,0.22)]">
          <div className="grid gap-0 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="p-10 lg:p-14">
              <p className="text-xs font-bold uppercase tracking-[0.34em] text-white/82">Account Center</p>
              <h1 className="mt-6 max-w-2xl text-5xl font-black leading-[0.95] tracking-tighter">{profile.username}</h1>
              <p className="mt-4 text-lg font-semibold text-white">{profile.role}</p>
              <p className="mt-8 max-w-2xl text-base leading-8 text-white/92">{profile.bio}</p>

              <div className="mt-10 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-2xl bg-white px-5 py-3 text-sm font-bold text-[#163a80] transition hover:-translate-y-px"
                >
                  <MaterialIcon name="manage_accounts" className="text-base" />
                  重置密码
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-2xl border border-white/36 bg-white/18 px-5 py-3 text-sm font-bold text-white transition hover:-translate-y-px"
                >
                  <MaterialIcon name="upload" className="text-base" />
                  更换头像
                </button>
                <button
                  type="button"
                  onClick={logout}
                  className="inline-flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-3 text-sm font-bold text-rose-700 transition hover:-translate-y-px"
                >
                  <MaterialIcon name="close" className="text-base" />
                  退出登录
                </button>
              </div>
            </div>

            <div className="relative flex items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.22),transparent_20%),linear-gradient(180deg,rgba(255,255,255,0.12)_0%,rgba(15,23,42,0.08)_100%)] p-10">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.14),transparent_54%)]" />
              <div className="relative text-center">
                <div className="mx-auto grid h-44 w-44 place-items-center rounded-[40px] border border-white/34 bg-[linear-gradient(145deg,rgba(255,255,255,0.3),rgba(255,255,255,0.12))] text-5xl font-black tracking-[-0.08em] text-white shadow-[0_24px_48px_rgba(15,23,42,0.18)] backdrop-blur-xl">
                  LX
                </div>
                <div className="mt-6 rounded-full border border-white/28 bg-white/16 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md">
                  当前头像
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-8 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <GlassPanel className="border border-[#d6dfef] bg-white p-8 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
            <div className="mb-8 flex items-center gap-3">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#eaf1ff] text-[#2357b8]">
                <MaterialIcon name="account_circle" className="text-xl" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Profile Details</p>
                <h2 className="mt-1 text-2xl font-black text-[#17304a]">个人资料</h2>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {accountFields.map(([label, value]) => (
                <div key={label} className="rounded-[24px] border border-[#dde6f5] bg-[#f8fbff] p-5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#60738f]">{label}</p>
                  <p className="mt-3 text-base font-bold text-[#17304a]">{value}</p>
                </div>
              ))}
            </div>
          </GlassPanel>

          <div className="space-y-8">
            <GlassPanel className="border border-[#d6dfef] bg-white p-8 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
              <div className="mb-6 flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#eaf1ff] text-[#2357b8]">
                  <MaterialIcon name="settings" className="text-xl" />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Security</p>
                  <h2 className="mt-1 text-2xl font-black text-[#17304a]">账号安全</h2>
                </div>
              </div>

              <div className="space-y-4">
                {securityItems.map(([label, value]) => (
                  <div key={label} className="rounded-[22px] border border-[#dde6f5] bg-[#f8fbff] px-5 py-4">
                    <p className="text-sm font-bold text-[#17304a]">{label}</p>
                    <p className="mt-1 text-sm text-[#5f7088]">{value}</p>
                  </div>
                ))}
              </div>
            </GlassPanel>

            <GlassPanel className="border border-[#d6dfef] bg-white p-8 shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
              <div className="mb-6 flex items-center gap-3">
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#eaf1ff] text-[#2357b8]">
                  <MaterialIcon name="dashboard" className="text-xl" />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#5b6f8d]">Quick Access</p>
                  <h2 className="mt-1 text-2xl font-black text-[#17304a]">快捷入口</h2>
                </div>
              </div>

              <div className="space-y-3">
                {quickLinks.map((item) => (
                  <a
                    key={item.title}
                    href={item.href}
                    className="flex items-center justify-between rounded-[22px] border border-[#dde6f5] bg-[#f8fbff] px-5 py-4 transition hover:-translate-y-px hover:border-[#9cb9f2] hover:bg-white"
                  >
                    <div className="flex items-center gap-4">
                      <div className="grid h-11 w-11 place-items-center rounded-2xl bg-[#eaf1ff] text-[#2357b8]">
                        <MaterialIcon name={item.icon} className="text-lg" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-[#17304a]">{item.title}</p>
                        <p className="mt-1 text-xs text-[#5f7088]">{item.subtitle}</p>
                      </div>
                    </div>
                    <MaterialIcon name="arrow_forward" className="text-[#2357b8]" />
                  </a>
                ))}
              </div>
            </GlassPanel>
          </div>
        </div>
      </main>
    </AppSurface>
  );
}
