import { routeHref, routes, type RouteKey } from "../routing";
import { MaterialIcon } from "../../shared/ui";
import { cx } from "../../shared/utils";

const sidebarNavItems = [
  { route: routes.ai, label: "AI 助教", icon: "quiz" },
  { route: routes.graph, label: "知识图谱", icon: "hub" },
  { route: routes.video, label: "课程视频", icon: "play_circle" },
  { route: routes.knowledge, label: "课程知识库", icon: "menu_book" },
  { route: routes.edit, label: "课程编辑", icon: "settings_suggest" },
] as const;

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
          ? "border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent-strong)] shadow-[0_10px_24px_var(--accent-shadow)]"
          : "border-transparent text-[var(--muted-text)] hover:-translate-y-px hover:border-[var(--shell-border)] hover:bg-[var(--surface-elevated)] hover:text-[var(--accent)]",
      )}
    >
      <span
        className={cx(
          "absolute bottom-2 left-0 top-2 w-1 rounded-r-full transition-colors",
          active ? "bg-[var(--accent)]" : "bg-transparent group-hover:bg-[var(--track-color)]",
        )}
      />
      <span
        className={cx(
          "ml-2 grid h-10 w-10 place-items-center rounded-2xl border transition-[background-color,color,border-color]",
          active
            ? "border-[var(--accent-border)] bg-[var(--surface-elevated)] text-[var(--accent)]"
            : "border-[var(--shell-border)] bg-[var(--surface-subtle)] text-slate-400 group-hover:border-[var(--accent-border)] group-hover:bg-[var(--accent-soft)] group-hover:text-[var(--accent)]",
        )}
      >
        <MaterialIcon name={icon} fill={active} className="text-[20px]" />
      </span>
      <span>{label}</span>
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

export function SidebarBackLink({ href = routeHref(routes.home), label = "返回首页" }: { href?: string; label?: string }) {
  return (
    <a
      href={href}
      className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--shell-border)] bg-[var(--surface-elevated)] px-3 py-2 text-xs font-semibold text-[var(--accent-strong)] transition hover:border-[var(--accent-border)] hover:bg-[var(--accent-soft)]"
    >
      <MaterialIcon name="arrow_back" className="text-sm" />
      {label}
    </a>
  );
}
