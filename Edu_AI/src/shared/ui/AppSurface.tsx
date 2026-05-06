import type { PropsWithChildren } from "react";
import { cx } from "../utils";

export function AppSurface({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={cx(
        "min-h-screen bg-[var(--app-bg)] text-[var(--app-text)]",
        "[font-family:var(--font-sans)] [&_h1]:[font-family:var(--font-display)] [&_h2]:[font-family:var(--font-display)] [&_h3]:[font-family:var(--font-display)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
