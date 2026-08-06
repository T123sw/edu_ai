import type { ReactNode } from "react";
import { MaterialIcon, cx } from "../shared";

export type PageStateValue =
  | { kind: "loading"; title?: string; description?: string }
  | { kind: "empty"; title: string; description?: string; action?: ReactNode }
  | { kind: "error"; title?: string; description: string; action?: ReactNode }
  | { kind: "offline"; title?: string; description?: string; action?: ReactNode }
  | { kind: "forbidden"; title?: string; description?: string; action?: ReactNode }
  | { kind: "conflict"; title?: string; description?: string; action?: ReactNode };

const presentation = {
  loading: { icon: "schedule", title: "正在加载课程" },
  empty: { icon: "folder_open", title: "暂时没有内容" },
  error: { icon: "help", title: "页面加载失败" },
  offline: { icon: "travel_explore", title: "网络连接已中断" },
  forbidden: { icon: "visibility", title: "当前账号无权访问" },
  conflict: { icon: "campaign", title: "内容已在别处更新" },
} as const;

export function PageState({ state, className }: { state: PageStateValue; className?: string }) {
  const defaults = presentation[state.kind];
  const action = "action" in state ? state.action : null;
  return (
    <section className={cx("page-state", `page-state--${state.kind}`, className)} aria-live="polite">
      <span className="page-state__icon"><MaterialIcon name={defaults.icon} /></span>
      <h2>{state.title ?? defaults.title}</h2>
      {state.description ? <p>{state.description}</p> : null}
      {action ? <div className="page-state__action">{action}</div> : null}
    </section>
  );
}
