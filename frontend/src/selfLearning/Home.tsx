import { useState, type FormEvent } from "react";
import { allResources, completion, type Classroom } from "./model";
import { Brand, Icon } from "./ui";

type Props = {
  rooms: Classroom[];
  shared: Classroom[];
  canPublish: boolean;
  onCreate: (text: string) => void;
  onOpen: (room: Classroom, shared?: boolean) => void;
  onPublish: () => void;
};
export function Cover({ room }: { room: Classroom }) {
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
  shared,
  onOpen,
}: {
  room: Classroom;
  shared?: boolean;
  onOpen: () => void;
}) {
  const resources = allResources(room);
  const selected = resources.find((r) => r.id === room.selectedId);
  return (
    <button className="sl-class-card" onClick={onOpen}>
      <Cover room={room} />
      <div className="sl-card-copy">
        <h3>{room.title}</h3>
        <p>
          {shared
            ? `${room.publisher} · ${room.chapters.length} 个学习主题`
            : `上次学到：${selected?.topic || "第一节"}`}
        </p>
        <div className="sl-card-meta">
          {shared ? (
            <>
              <span>共享课堂</span>
              <span>
                开始学习 <Icon name="arrow" size={14} />
              </span>
            </>
          ) : (
            <>
              <span>
                已完成 {completion(room)} / {resources.length} 份
              </span>
              <span>
                继续学习 <Icon name="arrow" size={14} />
              </span>
            </>
          )}
        </div>
        {!shared && (
          <div className="sl-card-progress">
            <i
              style={{
                width: `${(completion(room) / resources.length) * 100}%`,
              }}
            />
          </div>
        )}
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
}: Props) {
  const [prompt, setPrompt] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const matches = (r: Classroom) =>
    `${r.title} ${r.goal}`.toLowerCase().includes(query.trim().toLowerCase());
  function submit(e: FormEvent) {
    e.preventDefault();
    if (prompt.trim()) onCreate(prompt.trim());
  }
  const recent = [...rooms]
    .filter(matches)
    .sort((a, b) => b.updatedAt - a.updatedAt);
  return (
    <main className="sl-home">
      <section className="sl-home-hero">
        <Brand large />
        <h1>让好奇，成为你的下一堂课。</h1>
        <p>告诉我你想学什么，其余的交给学习 Agent。</p>
        <form className="sl-prompt" onSubmit={submit}>
          <div className="sl-prompt-greeting">
            <span className="sl-mini-avatar">你</span> 今天，想探索什么？
            <span className="sl-agent-ready">
              <i />
              学习 Agent
            </span>
          </div>
          <textarea
            aria-label="学习知识点与目标"
            placeholder="例如：我会 Python，希望系统学习 Agent，能独立开发一个应用。"
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
            <span>
              <Icon name="spark" size={15} />
              自动规划 · 整理资料 · 生成课堂
            </span>
            <button
              className="sl-primary"
              disabled={!prompt.trim()}
              type="submit"
            >
              开始学习 <Icon name="arrow" size={17} />
            </button>
          </div>
        </form>
        <div className="sl-suggestions">
          {[
            "从零开始学习 Agent",
            "用 Python 做数据分析",
            "培养我的设计思维",
          ].map((text) => (
            <button key={text} onClick={() => setPrompt(text)}>
              {text}
              <Icon name="arrow" size={13} />
            </button>
          ))}
        </div>
      </section>
      <div className="sl-home-library">
        <section>
          <div className="sl-section-heading">
            <h2>
              <Icon name="clock" size={18} />
              最近学习 <span>{rooms.length}</span>
            </h2>
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
              {recent.length > 3 && (
                <button
                  className="sl-text-button"
                  onClick={() => setExpanded(!expanded)}
                >
                  {expanded ? "收起" : "查看全部"}
                </button>
              )}
            </div>
          </div>
          {recent.length ? (
            <div className="sl-card-grid">
              {recent.slice(0, expanded ? undefined : 3).map((r) => (
                <ClassroomCard key={r.id} room={r} onOpen={() => onOpen(r)} />
              ))}
            </div>
          ) : (
            <p className="sl-inline-empty">
              {query
                ? "没有找到相关课堂，换个关键词试试。"
                : "你的第一段学习旅程，从上面的输入框开始。"}
            </p>
          )}
        </section>
        <section>
          <div className="sl-section-heading">
            <h2>
              <Icon name="book" size={18} />
              发现共享课堂
            </h2>
            {canPublish && (
              <button className="sl-text-button" onClick={onPublish}>
                <Icon name="upload" size={16} />
                上传课堂
              </button>
            )}
          </div>
          <div className="sl-card-grid">
            {shared.filter(matches).map((r) => (
              <ClassroomCard
                key={r.id}
                room={r}
                shared
                onOpen={() => onOpen(r, true)}
              />
            ))}
          </div>
          {!shared.filter(matches).length && (
            <p className="sl-inline-empty">暂无匹配的共享课堂。</p>
          )}
        </section>
      </div>
      <footer className="sl-home-footer">
        每一次好奇，都值得认真探索。
        <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>
      </footer>
    </main>
  );
}
