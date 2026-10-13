import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { allResources, completion, type Classroom } from "./model";
import { Icon } from "./ui";

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
  preparationTasks?: ReactNode;
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
  shared = false,
  onOpen,
}: {
  room: Classroom;
  shared?: boolean;
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
        <span className="sl-course-type">{shared || room.sourceId ? '共享课堂' : '我的课堂'} · {room.chapters.length} 个主题</span>
        <h3>{room.title}</h3>
        <div className="sl-course-meta"><span>已学完 {completion(room)} / {allResources(room).length} 份资料</span><Icon name="arrow" size={16} /></div>
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
  canCreateFromUploads = false,
  preparationOptions,
  preparationTasks,
}: Props) {
  const [prompt, setPrompt] = useState("");
  const promptRef = useRef<HTMLTextAreaElement>(null);
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
  const resume = [...rooms].sort((a, b) => b.updatedAt - a.updatedAt)[0];
  const resumeChapter = resume?.chapters.find(c => c.resources.some(r => r.id === resume.selectedId));
  return (
    <main className="sl-home sl-space-home">
      <section className="sl-home-hero">
        <div className="sl-hero-copy"><span className="sl-kicker">你的学习与探索空间</span>
          <h1>学有所思，<br /><em>让想法发生。</em></h1>
          <p>从一堂为你准备的课开始，<br />把理解变成问题，把问题带进实践。</p>
          <div className="sl-hero-path"><span><Icon name="book" size={17} />理解知识</span><i /><span><Icon name="flask" size={17} />探索问题</span><i /><span><Icon name="folder" size={17} />积累成果</span></div>
        </div>
        <form id="course-create" className={`sl-prompt${preparationOptions ? ' sl-prompt-with-options' : ''}`} onSubmit={submit}>
          <div className="sl-prompt-heading"><span><Icon name="spark" size={18} />从一个学习目标开始</span><small>AI 课程</small></div>
          <textarea
            ref={promptRef}
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
          {preparationOptions}
          <div className="sl-prompt-bottom">
            <span>{live ? '提交后为你研究资料并准备课程' : '体验课程学习流程'}</span>
            <button
              className="sl-primary"
              disabled={!prompt.trim() && !canCreateFromUploads}
              type="submit"
            >
              开始学习 <Icon name="arrow" size={17} />
            </button>
          </div>
        </form>
      </section>
      <section className="sl-module-grid" aria-label="探索学习方式">
        <button className="sl-module-card learning" onClick={() => { promptRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); promptRef.current?.focus({ preventScroll: true }); }}><span className="sl-module-icon"><Icon name="book" size={23} /></span><div><span className="sl-module-tag">现在开始</span><h2>课程学习</h2><p>围绕目标与资料，系统理解一个主题。</p></div><Icon name="arrow" size={19} /></button>
        <a className="sl-module-card research" href="#/research"><span className="sl-module-icon"><Icon name="flask" size={23} /></span><div><span className="sl-module-tag">先准备项目</span><h2>科研实践</h2><p>带着课程中的问题，整理实践想法。</p></div><Icon name="arrow" size={19} /></a>
        <a className="sl-module-card interview" href="#/interview"><span className="sl-module-icon"><Icon name="briefcase" size={23} /></span><div><span className="sl-module-tag">独立产品 · 筹备中</span><h2>面试 Agent</h2><p>围绕真实求职，练习下一次面试。</p></div><Icon name="arrow" size={19} /></a>
      </section>
      {resume && <section className="sl-resume" aria-label="继续上次学习"><span className="sl-resume-icon"><Icon name="play" size={21} /></span><div><small>接着上次的思路</small><h2>{resume.title}</h2><p>{resumeChapter ? `当前知识点：${resumeChapter.title}` : '回到课堂，继续探索'}</p></div><button className="sl-primary" onClick={() => onOpen(resume)}>继续学习<Icon name="arrow" size={17} /></button></section>}
      {preparationTasks}
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
                shared
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
        Edu AI · 把每一次好奇，变成下一步探索。
        {!live && <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>}
      </footer>
    </main>
  );
}
