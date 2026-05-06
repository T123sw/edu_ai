import { useState, type PropsWithChildren } from "react";
import { MaterialIcon } from "../../shared/ui";
import { cx } from "../../shared/utils";

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
          "fixed left-0 top-0 z-50 hidden w-64 flex-col border-r border-[var(--shell-border)] bg-[var(--shell-surface)] shadow-[10px_0_30px_var(--shell-shadow)] transition-transform duration-200 lg:flex",
          collapsed ? "-translate-x-[calc(100%-18px)]" : "translate-x-0",
          className,
        )}
      >
        <button
          type="button"
          onClick={() => setCollapsed((current) => !current)}
          className="absolute -right-4 top-6 z-10 flex h-8 w-8 items-center justify-center rounded-full border border-[var(--shell-border)] bg-[var(--shell-surface)] text-[var(--accent-strong)] shadow-md"
        >
          <MaterialIcon name={collapsed ? "chevron_right" : "chevron_left"} className="text-base" />
        </button>
        {children}
      </aside>
    </>
  );
}
