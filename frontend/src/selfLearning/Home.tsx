import { useState, type FormEvent } from "react";
import { type Classroom } from "./model";
import { Brand, Icon } from "./ui";

type Props = {
  rooms: Classroom[];
  shared: Classroom[];
  canPublish: boolean;
  onCreate: (text: string) => void;
  onOpen: (room: Classroom, shared?: boolean) => void;
  onPublish: () => void;
  live?: boolean;
};
export function Cover({ room }: { room: Pick<Classroom, "tone"> }) {
  const python = room.tone === "mint";
  const design = room.tone === "peach";
  return (
    <div className={`sl-cover ${room.tone}`} aria-hidden="true">
      <span className="sl-cover-caption">
        {python
          ? "THINK IN PYTHON"
          : design
            ? "MAKE IDEAS VISIBLE"
            : "LEARN · THINK · BUILD"}
      </span>
      <div className="sl-cover-art">
        {python ? (
          <span className="sl-code-art">
            {"{ }"}
            <small>hello, world.</small>
          </span>
        ) : design ? (
          <div className="sl-shapes">
            <i />
            <i />
            <i />
          </div>
        ) : (
          <div className="sl-agent-art">
            <span />
            <b>
              <Icon name="spark" size={30} />
            </b>
            <span />
          </div>
        )}
      </div>
      <span className="sl-cover-bottom">
        {python
          ? "把想法写成代码"
          : design
            ? "让灵感成为可能"
            : "从理解到独立创造"}
        <Icon name="arrow" size={16} />
      </span>
    </div>
  );
}
function ClassroomCard({
  room,
  onOpen,
}: {
  room: Classroom;
  onOpen: () => void;
}) {
  return (
    <button className="sl-class-card" onClick={onOpen} title={room.title}>
      <div className={`sl-course-preview ${room.tone}`} aria-hidden="true">
        <div className="sl-preview-paper">
          <strong>{room.chapters[0]?.title || room.title}</strong>
          <div className="sl-preview-rule" />
          <div className="sl-preview-content">
            <div className="sl-preview-outline">
              {room.chapters.slice(0, 3).map((chapter, index) => (
                <div key={chapter.id}><i>{index + 1}</i><span>{chapter.title}</span></div>
              ))}
            </div>
            <div className="sl-preview-diagram">
              <span /><div><i /><i /><i /></div><b />
            </div>
          </div>
        </div>
      </div>
      <div className="sl-card-copy">
        <h3>{room.title}</h3>
      </div>
    </button>
  );
}
export function Home({
  rooms,
  shared,
  canPublish,
  onCreate,
  onOpen,
  onPublish,
  live,
}: Props) {
  const [prompt, setPrompt] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [sharedExpanded, setSharedExpanded] = useState(false);
  const [origin, setOrigin] = useState("all");
  const matches = (r: Classroom) =>
    `${r.title} ${r.goal}`.toLowerCase().includes(query.trim().toLowerCase());
  function submit(e: FormEvent) {
    e.preventDefault();
    if (prompt.trim()) onCreate(prompt.trim());
  }
  const recent = [...rooms]
    .filter(matches)
    .filter(r => origin === "all" || (origin === "shared" ? !!r.sourceId : !r.sourceId))
    .sort((a, b) => b.updatedAt - a.updatedAt);
  const sharedMatches = shared.filter(matches);
  return (
    <main className="sl-home">
      <section className="sl-home-hero">
        <Brand large />
        <h1>让好奇，成为你的下一堂课。</h1>
        <form className="sl-prompt" onSubmit={submit}>
          <textarea
            aria-label="学习知识点与目标"
            placeholder="想学什么？说说你的学习目标…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            maxLength={1000}
            onKeyDown={(e) => {
              if (
                (e.ctrlKey || e.metaKey) &&
                e.key === "Enter" &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (prompt.trim()) onCreate(prompt.trim());
              }
            }}
          />
          <div className="sl-prompt-bottom">
            <button
              className="sl-primary"
              disabled={!prompt.trim()}
              type="submit"
            >
              开始学习 <Icon name="arrow" size={17} />
            </button>
          </div>
        </form>
      </section>
      <div className="sl-home-library">
        <section aria-label="最近学习">
          <div className="sl-section-heading">
            <h2>
              <Icon name="clock" size={18} />
              最近学习 <span>{rooms.length}</span>
            </h2>
          <div className="sl-recent-filters" aria-label="课堂来源">
            {[["all", "全部"], ["own", "自己生成"], ["shared", "共享课堂"]].map(([id, label]) => <button key={id} aria-pressed={origin === id} onClick={() => { setOrigin(id); setExpanded(false); }}>{label}<small>{rooms.filter(r => id === "all" || (id === "shared" ? !!r.sourceId : !r.sourceId)).length}</small></button>)}
          </div>
            <div className="sl-inline">
              {search && (
                <input
                  className="sl-small-input"
                  aria-label="搜索课堂"
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索课堂…"
                />
              )}
              <button
                className="sl-icon-button"
                onClick={() => {
                  setSearch(!search);
                  setQuery("");
                }}
                aria-label={search ? "关闭课堂搜索" : "搜索课堂"}
              >
                <Icon name={search ? "close" : "search"} size={18} />
              </button>
              {recent.length > 4 && (
                <button
                  className="sl-text-button"
                  onClick={() => setExpanded(!expanded)}
                  aria-expanded={expanded}
                >
                  {expanded ? "收起" : "查看全部"}
                </button>
              )}
            </div>
          </div>
          {recent.length ? (
            <div className="sl-card-grid">
              {recent.slice(0, expanded ? undefined : 4).map((r) => (
                <ClassroomCard key={r.id} room={r} onOpen={() => onOpen(r)} />
              ))}
            </div>
          ) : (
            <p className="sl-inline-empty">
              {query
                ? "没有找到相关课堂，换个关键词试试。"
                : origin === "shared" ? "还没有学习过共享课堂，可以从下方选择一堂开始。" : "你的第一段学习旅程，从上面的输入框开始。"}
            </p>
          )}
        </section>
        <section aria-label="发现共享课堂">
          <div className="sl-section-heading">
            <h2>
              <Icon name="book" size={18} />
              发现共享课堂
            </h2>
            <div className="sl-inline">
              {sharedMatches.length > 4 && (
                <button className="sl-text-button" aria-expanded={sharedExpanded} onClick={() => setSharedExpanded(!sharedExpanded)}>
                  {sharedExpanded ? "收起" : "查看全部"}
                </button>
              )}
            {canPublish && (
              <button className="sl-text-button" onClick={onPublish}>
                <Icon name="upload" size={16} />
                {live ? "共享我的课堂" : "上传课堂"}
              </button>
            )}
            </div>
          </div>
          <div className="sl-card-grid">
            {sharedMatches.slice(0, sharedExpanded ? undefined : 4).map((r) => (
              <ClassroomCard
                key={r.id}
                room={r}
                onOpen={() => onOpen(r, true)}
              />
            ))}
          </div>
          {!sharedMatches.length && (
            <p className="sl-inline-empty">暂无匹配的共享课堂。</p>
          )}
        </section>
      </div>
      <footer className="sl-home-footer">
        每一次好奇，都值得认真探索。
        {!live && <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>}
      </footer>
    </main>
  );
}
