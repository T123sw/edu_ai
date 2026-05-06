import type { PropsWithChildren } from "react";
import { cx } from "../utils";

export function GlassPanel({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cx(
        "rounded-[28px] bg-[var(--panel-surface)] backdrop-blur-xl shadow-[0_16px_32px_var(--panel-shadow)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
