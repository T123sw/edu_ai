import {
  createContext,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
  type ReactNode,
} from "react";

export function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export const routes = {
  workspace: "workspace",
  course: "course",
  courseDetail: "course-detail",
  ai: "ai",
  home: "home",
  profile: "profile",
  graph: "graph",
  ppt: "ppt",
  resources: "resources",
  knowledge: "knowledge",
  edit: "edit",
  // Dev-only, not in any nav — Phase 3 player smoke test (SPEC-08 §6 / ACC-08 §3.2).
  playerSmoke: "player-smoke",
  // Standalone 1920x1080 route consumed by the Phase 5 headless video recorder.
  videoRender: "video-render",
  // Real feature (not dev-only): AI 课件生成 studio，从课程详情页进入。
  classroomStudio: "classroom-studio",
  // Real feature (not dev-only): 播放一份已生成的课件。
  // Reached via #classroom-player?course_id=...&classroom_id=...
  classroomPlayer: "classroom-player",
} as const;

export type RouteKey = (typeof routes)[keyof typeof routes];
export type ThemeName = "ocean" | "forest" | "sunset" | "dark";

export type CourseSummary = {
  id: string;
  module: string;
  title: string;
  uppercaseTitle: string;
  instructor: string;
  progress: number;
  image: string;
  accent: string;
  summary: string;
};

export const defaultCourse: CourseSummary = {
  id: "quantum-advanced",
  module: "模块 4",
  title: "高等量子力学",
  uppercaseTitle: "ADVANCED QUANTUM MECHANICS",
  instructor: "Dr. Eleanor Stone",
  progress: 65,
  image: "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1200&q=80",
  accent: "from-[#0f172a] via-[#1d4ed8] to-[#60a5fa]",
  summary: "聚焦波函数演化、观测与知识图谱联动的高阶课程。",
};

type AppShellContextValue = {
  selectedCourse: CourseSummary | null;
  setSelectedCourse: (course: CourseSummary | null) => void;
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  logout: () => void;
};

const AppShellContext = createContext<AppShellContextValue | null>(null);

const sidebarNavItems = [
  { route: routes.ai, label: "问答", icon: "quiz" },
  { route: routes.graph, label: "知识图谱", icon: "hub" },
  { route: routes.classroomStudio, label: "AI 课堂", icon: "play_circle" },
  { route: routes.knowledge, label: "课程知识库", icon: "menu_book" },
  { route: routes.edit, label: "详情编辑", icon: "settings_suggest" },
] as const;

export function routeHref(route: RouteKey) {
  return `#${route}`;
}

export function AppShellProvider({
  children,
  selectedCourse,
  setSelectedCourse,
  theme,
  setTheme,
  logout,
}: PropsWithChildren<AppShellContextValue>) {
  const value = useMemo(
    () => ({ selectedCourse, setSelectedCourse, theme, setTheme, logout }),
    [selectedCourse, setSelectedCourse, theme, setTheme, logout],
  );

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const value = useContext(AppShellContext);

  if (!value) {
    throw new Error("useAppShell must be used inside AppShellProvider.");
  }

  return value;
}

export function MaterialIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
  fill?: boolean;
}) {
  const iconGlyphs: Record<string, string> = {
    account_circle: "◉",
    account_tree: "⑂",
    arrow_back: "←",
    arrow_forward: "→",
    article: "▤",
    auto_awesome: "✦",
    auto_graph: "◔",
    campaign: "📢",
    check_circle: "✓",
    chevron_left: "‹",
    chevron_right: "›",
    close: "×",
    close_fullscreen: "⤢",
    dashboard: "⊞",
    database: "◫",
    description: "≣",
    download: "↓",
    edit_note: "✎",
    expand_less: "▴",
    expand_more: "▾",
    fact_check: "☑",
    folder_open: "⊟",
    forum: "💬",
    fullscreen: "⛶",
    help: "?",
    hub: "◎",
    last_page: "»",
    layers: "▤",
    lightbulb: "💡",
    manage_accounts: "⚙",
    menu_book: "☰",
    mic: "🎤",
    more_vert: "⋮",
    notifications: "🔔",
    pan_tool_alt: "✋",
    perm_media: "▣",
    person: "👤",
    picture_as_pdf: "PDF",
    play_arrow: "▶",
    play_circle: "▷",
    quiz: "?",
    school: "🎓",
    search: "⌕",
    schedule: "◷",
    send: "➤",
    settings: "⚙",
    settings_suggest: "⚙",
    share: "⤴",
    skip_next: "⏭",
    slideshow: "▭",
    smart_toy: "🤖",
    star: "★",
    travel_explore: "⌖",
    upload: "↑",
    upload_file: "⇪",
    visibility: "◉",
    volume_up: "🔊",
    zoom_in: "+",
  };

  return (
    <span className={cx("app-icon", className)} aria-hidden="true" title={name}>
      {iconGlyphs[name] ?? "•"}
    </span>
  );
}

export function AppSurface({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cx(
        "min-h-screen bg-(--app-bg) text-(--app-text)",
        "font-sans [&_h1]:[font-family:var(--font-display)] [&_h2]:[font-family:var(--font-display)] [&_h3]:[font-family:var(--font-display)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SidebarDock({
  children,
  className,
  spacerClassName,
}: PropsWithChildren<{ className?: string; spacerClassName?: string }>) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      <div
        aria-hidden="true"
        className={cx("hidden flex-none transition-[width] duration-200 lg:block", collapsed ? "w-0" : "w-64", spacerClassName)}
      />
      <aside
        className={cx(
          "fixed left-0 top-0 z-50 hidden w-64 flex-col border-r border-(--shell-border) bg-(--shell-surface) shadow-[10px_0_30px_var(--shell-shadow)] transition-transform duration-200 lg:flex",
          collapsed ? "-translate-x-[calc(100%-18px)]" : "translate-x-0",
          className,
        )}
      >
        <button
          type="button"
          onClick={() => setCollapsed((current) => !current)}
          className="absolute -right-4 top-6 z-10 flex h-8 w-8 items-center justify-center rounded-full border border-(--shell-border) bg-(--shell-surface) text-(--accent-strong) shadow-md"
        >
          <MaterialIcon name={collapsed ? "chevron_right" : "chevron_left"} className="text-base" />
        </button>
        {children}
      </aside>
    </>
  );
}

export function GlassPanel({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cx(
        "rounded-[28px] bg-(--panel-surface) backdrop-blur-xl shadow-[0_16px_32px_var(--panel-shadow)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h3 className="text-xl font-extrabold tracking-tight text-(--accent-strong)">{title}</h3>
        {subtitle ? <p className="mt-1 text-sm text-(--muted-text)">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function ProgressBar({
  value,
  className,
  barClassName,
}: {
  value: number;
  className?: string;
  barClassName?: string;
}) {
  return (
    <div className={cx("h-1.5 overflow-hidden rounded-full bg-(--track-color)", className)}>
      <div className={cx("h-full rounded-full bg-(--accent)", barClassName)} style={{ width: `${value}%` }} />
    </div>
  );
}

export function SidebarLink({
  label,
  icon,
  href,
  active,
}: {
  label: string;
  icon: string;
  href: string;
  active?: boolean;
}) {
  return (
    <a
      href={href}
      className={cx(
        "group relative flex items-center gap-3 rounded-[18px] border px-3 py-3 text-sm font-semibold transition-[background-color,color,border-color,box-shadow,transform] duration-200",
        active
          ? "border-(--accent-border) bg-(--accent-soft) text-(--accent-strong) shadow-[0_10px_24px_var(--accent-shadow)]"
          : "border-transparent text-(--muted-text) hover:-translate-y-px hover:border-(--shell-border) hover:bg-(--surface-elevated) hover:text-(--accent)",
      )}
    >
      <span
        className={cx(
          "absolute bottom-2 left-0 top-2 w-1 rounded-r-full transition-colors",
          active ? "bg-(--accent)" : "bg-transparent group-hover:bg-(--track-color)",
        )}
      />
      <span
        className={cx(
          "ml-2 grid h-10 w-10 place-items-center rounded-2xl border transition-[background-color,color,border-color]",
          active
            ? "border-(--accent-border) bg-(--surface-elevated) text-(--accent)"
            : "border-(--shell-border) bg-(--surface-subtle) text-slate-400 group-hover:border-(--accent-border) group-hover:bg-(--accent-soft) group-hover:text-(--accent)",
        )}
      >
        <MaterialIcon name={icon} fill={active} className="text-[20px]" />
      </span>
      <span className="tracking-[0.01em]">{label}</span>
    </a>
  );
}

export function SidebarNav({
  activeRoute,
  className,
}: {
  activeRoute: RouteKey;
  className?: string;
}) {
  return (
    <nav className={cx("flex flex-1 flex-col gap-2", className)}>
      {sidebarNavItems.map((item) => (
        <SidebarLink
          key={item.route}
          label={item.label}
          icon={item.icon}
          href={routeHref(item.route)}
          active={activeRoute === item.route}
        />
      ))}
    </nav>
  );
}

export function SidebarBackLink({ href = routeHref(routes.home), label = "返回主页" }: { href?: string; label?: string }) {
  return (
    <a
      href={href}
      className="mb-4 inline-flex items-center gap-2 rounded-full border border-(--shell-border) bg-(--surface-elevated) px-3 py-2 text-xs font-semibold text-(--accent-strong) transition hover:border-(--accent-border) hover:bg-(--accent-soft)"
    >
      <MaterialIcon name="arrow_back" className="text-sm" />
      {label}
    </a>
  );
}

export function ThemeCustomizer() {
  const { theme, setTheme } = useAppShell();
  const [open, setOpen] = useState(false);
  const themes: Array<{ id: ThemeName; label: string; preview: string; note: string }> = [
    { id: "ocean", label: "海蓝", preview: "from-[#0b5bd3] to-[#8ec5ff]", note: "默认教学风格" },
    { id: "forest", label: "森绿", preview: "from-[#1d6b3f] to-[#9dd8b7]", note: "适合长时间阅读" },
    { id: "sunset", label: "日落", preview: "from-[#b85a2b] to-[#f6c28b]", note: "更暖的展示氛围" },
    { id: "dark", label: "暗色", preview: "from-[#0f172a] to-[#475569]", note: "降低眩光" },
  ];

  return (
    <div className="fixed bottom-5 right-5 z-120">
      {open ? (
        <div className="w-72 rounded-[24px] border border-[#bfdbfe] bg-linear-to-br from-[#f8fbff] via-[#eef6ff] to-[#e0f2fe] p-4 shadow-[0_24px_60px_rgba(37,99,235,0.22)] backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-bold text-[#1d4ed8]">个人账号设置</div>
              <div className="text-xs text-[#64748b]">修改界面色调与显示偏好</div>
            </div>
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full border border-[#bfdbfe] bg-white/70 text-[#64748b] transition hover:border-[#60a5fa] hover:bg-[#dbeafe] hover:text-[#1d4ed8]"
              onClick={() => setOpen(false)}
              type="button"
            >
              <MaterialIcon name="close" className="text-base" />
            </button>
          </div>
          <div className="space-y-2">
            {themes.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTheme(item.id)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition duration-200",
                  theme === item.id
                    ? "border-[#60a5fa] bg-white shadow-[0_10px_24px_rgba(59,130,246,0.18)]"
                    : "border-[#dbeafe] bg-white/65 hover:border-[#93c5fd] hover:bg-white/90",
                )}
              >
                <span className={`h-9 w-9 rounded-full bg-linear-to-br ${item.preview}`} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-[#0f172a]">{item.label}</span>
                  <span className="block text-xs text-[#64748b]">{item.note}</span>
                </span>
                {theme === item.id ? (
                  <span className="rounded-full bg-[#dbeafe] px-2 py-1 text-[10px] font-semibold text-[#1d4ed8]">
                    当前
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="ml-auto mt-3 flex h-12 w-12 items-center justify-center rounded-full border border-[#93c5fd] bg-linear-to-br from-[#2563eb] to-[#0ea5e9] text-white shadow-[0_18px_36px_rgba(37,99,235,0.35)] transition hover:from-[#1d4ed8] hover:to-[#0284c7]"
      >
        <MaterialIcon name="manage_accounts" className="text-xl" />
      </button>
    </div>
  );
}

export function Badge({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", className)}>
      {children}
    </span>
  );
}
