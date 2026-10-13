import { useState, type FormEvent, type ReactNode } from "react";
import { allResources, type Classroom } from "./model";
import { Brand, Icon } from "./ui";

type Props = {
  rooms: Classroom[];
  shared: Classroom[];
  canPublish: boolean;
  onCreate: (text: string) => void;
  onOpen: (room: Classroom, shared?: boolean) => void;
  onPublish: () => void;
  live?: boolean;
  canCreateFromUploads?: boolean;
  preparationOptions?: ReactNode;
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
function LearningIllustration() {
  return <svg className="sl-editorial-illustration" viewBox="0 0 360 250" fill="none" aria-hidden="true">
    <circle cx="221" cy="106" r="74" fill="#E6DFCA" />
    <circle cx="264" cy="50" r="20" fill="#BD693F" />
    <ellipse cx="186" cy="130" rx="139" ry="61" transform="rotate(-27 186 130)" stroke="#879789" strokeWidth="1" strokeDasharray="3 6" />
    <path d="M72 175 179 217 299 161 193 124Z" fill="#D9DBCC" />
    <path d="m77 155 101 39 117-49v15l-117 50-101-40Z" fill="#F8F5EC" stroke="#214B3D" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M179 194V91c-34-25-70-26-105-17v101c40-7 72-2 105 19Z" fill="#FAF8F1" stroke="#214B3D" strokeWidth="1.7" strokeLinejoin="round" />
    <path d="M179 194V91c32-20 65-28 105-25v101c-39-1-73 9-105 27Z" fill="#E7EAD9" stroke="#214B3D" strokeWidth="1.7" strokeLinejoin="round" />
    <path d="M92 93c22-3 43 1 63 10m-63 9c22-3 43 1 63 10m-63 9c22-3 43 1 47 3m60-32c20-9 41-14 65-14m-65 34c20-9 41-14 65-14m-65 33c13-6 26-10 40-12" stroke="#809181" strokeWidth="1.4" strokeLinecap="round" />
    <path d="m251 68 12-1v56l-6-5-6 8Z" fill="#BD693F" />
    <path d="M50 83v20m-10-10h20M307 195v14m-7-7h14" stroke="#BD693F" strokeWidth="1.5" />
    <circle cx="82" cy="47" r="4" fill="#214B3D" />
    <circle cx="311" cy="105" r="3" fill="#BD693F" />
    <path d="m109 224 54 1m66-7 24-1" stroke="#B3B8A8" strokeLinecap="round" />
  </svg>;
}

function ClassroomCard({ room, onOpen }: { room: Classroom; onOpen: () => void }) {
  return <button className="sl-class-card" onClick={onOpen} title={room.title}>
    <div className={`sl-course-preview ${room.tone}`} aria-hidden="true">
      <span className="sl-jacket-spine" />
      <div className="sl-jacket-label"><span>EDU AI</span><span>学习手记</span></div>
      <strong className="sl-jacket-title">{room.chapters[0]?.title || room.title}</strong>
      <svg className="sl-jacket-art" viewBox="0 0 160 100" fill="none"><ellipse cx="80" cy="51" rx="62" ry="27" transform="rotate(-28 80 51)" /><ellipse cx="80" cy="51" rx="62" ry="27" transform="rotate(28 80 51)" /><circle cx="80" cy="51" r="27" /><circle cx="130" cy="22" r="5" fill="currentColor" stroke="none" /></svg>
      <div className="sl-jacket-bottom"><span>{String(room.chapters.length).padStart(2, '0')} 个知识点</span><span>LEARN / EXPLORE</span></div>
    </div>
    <div className="sl-card-copy"><h3>{room.title}</h3><div className="sl-editorial-card-meta"><span>{allResources(room).length} 份学习资料</span><Icon name="arrow" size={16} /></div></div>
  </button>;
}
export function Home({
  rooms,
  shared,
  canPublish,
  onCreate,
  onOpen,
  onPublish,
  live,
  canCreateFromUploads = false,
  preparationOptions,
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
    if (prompt.trim() || canCreateFromUploads) onCreate(prompt.trim());
  }
  const recent = [...rooms]
    .filter(matches)
    .filter(r => origin === "all" || (origin === "shared" ? !!r.sourceId : !r.sourceId))
    .sort((a, b) => b.updatedAt - a.updatedAt);
  const sharedMatches = shared.filter(matches);
  return (
    <main className="sl-home sl-home-editorial">
      <div className="sl-editorial-masthead"><Brand /><span>一处安静的学习空间</span></div>
      <section className="sl-home-hero">
        <div className="sl-editorial-intro"><div className="sl-editorial-copy"><span className="sl-editorial-eyebrow"><i />为好奇心，留一页空白</span><h1 aria-label="让好奇，成为你的下一堂课。">让好奇，<br /><em>成为你的下一堂课。</em></h1><p>写下想学的，带上你的问题。<br className="sl-editorial-mobile-break" />从这里开始，把知识慢慢读懂。</p></div><LearningIllustration /></div>
        <form className={`sl-prompt${preparationOptions ? ' sl-prompt-with-options' : ''}`} onSubmit={submit}>
          <div className="sl-editorial-composer-heading"><span><Icon name="spark" size={17} />今天，想探索什么？</span><small>目标 · 基础 · 想解决的问题</small></div>
          <textarea
            aria-label="学习知识点与目标"
            placeholder={"- 我想学习 Agent\n- 希望能独立做出一个 AI 助手\n- 会一点 Python，Agent 还是零基础"}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            maxLength={2000}
            onKeyDown={(e) => {
              if (
                (e.ctrlKey || e.metaKey) &&
                e.key === "Enter" &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (prompt.trim() || canCreateFromUploads) onCreate(prompt.trim());
              }
            }}
          />
          <div className="sl-editorial-composer-toolbar">{preparationOptions}
          <div className="sl-prompt-bottom">
            <button
              className="sl-primary"
              disabled={!prompt.trim() && !canCreateFromUploads}
              type="submit"
            >
              开始学习 <Icon name="arrow" size={17} />
            </button>
          </div></div>
        </form>
        <div className="sl-editorial-hero-foot"><span>每一次理解，都从一个好问题开始。</span><span>LEARNING, AT YOUR PACE.</span></div>
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
        <span className="sl-editorial-footer-mark">Edu AI <i>／</i> 学无止境</span><p>每一次好奇，都值得认真探索。</p>
        {!live && <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>}
      </footer>
    </main>
  );
}
