import type { ReactNode } from "react";

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
        <h3 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">{title}</h3>
        {subtitle ? <p className="mt-1 text-sm text-[var(--muted-text)]">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}
