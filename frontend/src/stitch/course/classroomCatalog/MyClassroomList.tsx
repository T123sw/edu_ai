import { MaterialIcon } from "../../shared";
import type { MyClassroomItem, MyClassroomStatus } from "./myClassroomPresentation";

type MyClassroomListProps = {
  items: MyClassroomItem[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (classroomId: string) => void;
  onRetry: () => void;
};

const STATUS_LABELS: Record<MyClassroomStatus, string> = {
  ready: "可观看",
  generating: "生成中",
  failed: "生成失败",
  empty: "暂无内容",
};

export function MyClassroomList({
  items,
  loading,
  error,
  selectedId,
  onSelect,
  onRetry,
}: MyClassroomListProps) {
  return <section className="my-classroom-list" aria-labelledby="my-classroom-title">
    <header>
      <div><MaterialIcon name="video_library" /><strong id="my-classroom-title">我的课堂</strong></div>
      {!loading && !error ? <small>{items.length}</small> : null}
    </header>
    {loading ? <p className="my-classroom-list__message">正在加载个人课堂…</p> : null}
    {!loading && error ? <div className="my-classroom-list__message is-error">
      <span>个人课堂暂时无法加载</span><button type="button" onClick={onRetry}>重新加载</button>
    </div> : null}
    {!loading && !error && !items.length ? <p className="my-classroom-list__message">还没有个人生成的课堂</p> : null}
    {!loading && !error && items.length ? <ul>{items.map((item) => {
      const playable = item.status === "ready";
      return <li key={item.id}><button
        type="button"
        className={selectedId === item.id ? "is-selected" : undefined}
        disabled={!playable}
        aria-current={selectedId === item.id ? "page" : undefined}
        onClick={() => onSelect(item.id)}
      >
        <MaterialIcon name={playable ? "play_circle" : item.status === "failed" ? "error" : "schedule"} />
        <span><strong>{item.title}</strong><small>{STATUS_LABELS[item.status]}</small></span>
      </button></li>;
    })}</ul> : null}
  </section>;
}
