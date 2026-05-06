import type { PropsWithChildren } from "react";
import { cx } from "../utils";

export function Badge({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", className)}>
      {children}
    </span>
  );
}
