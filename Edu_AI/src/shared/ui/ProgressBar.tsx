import { cx } from "../utils";

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
    <div className={cx("h-1.5 overflow-hidden rounded-full bg-[var(--track-color)]", className)}>
      <div className={cx("h-full rounded-full bg-[var(--accent)]", barClassName)} style={{ width: `${value}%` }} />
    </div>
  );
}
