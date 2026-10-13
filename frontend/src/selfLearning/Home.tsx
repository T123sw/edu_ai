import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { allResources, completion, type Classroom } from "./model";
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
const startingPoints = [
  { title: "读懂 AI Agent", tag: "人工智能", icon: "spark", tone: "violet", text: "从基本原理，到搭建一个小助手", prompt: "我想系统学习 AI Agent，会一点 Python。希望理解工具调用与任务规划，并能独立搭建一个简单的助手。" },
  { title: "用 Python 分析数据", tag: "编程实践", icon: "studio", tone: "mint", text: "从一张表格，发现数据里的规律", prompt: "我想学习用 Python 分析数据，有基础编程经验。希望学会清洗表格数据、绘制图表，并完成一个小型分析项目。" },
  { title: "直观理解线性代数", tag: "数学基础", icon: "slides", tone: "peach", text: "用图形理解向量、矩阵与变换", prompt: "我想直观地理解线性代数，已有高中数学基础。请结合几何图形和具体例子，帮助我理解向量、矩阵与线性变换。" },
  { title: "学会阅读学术论文", tag: "研究方法", icon: "report", tone: "blue", text: "找到问题、方法与结论之间的联系", prompt: "我想学习如何阅读学术论文，是科研入门者。希望能辨别研究问题、理解实验设计，并写出有依据的阅读笔记。" },
];

function ClassroomCard({ room, shared = false, onOpen }: { room: Classroom; shared?: boolean; onOpen: () => void }) {
  const resources = allResources(room);
  return <button className="sl-class-card" onClick={onOpen} title={room.title}>
    <div className={`sl-course-preview ${room.tone}`} aria-hidden="true">
      <div className="sl-course-cover-heading"><span>课程一览</span><Icon name="book" size={22} /></div>
      <div className="sl-course-outline">{room.chapters.slice(0, 3).map((chapter, index) => <div key={chapter.id}><span>0{index + 1}</span><strong>{chapter.title}</strong></div>)}</div>
      {!room.chapters.length && <span className="sl-course-outline-empty">从一个学习目标开始</span>}
    </div>
    <div className="sl-card-copy">
      <span className="sl-course-origin">{shared || room.sourceId ? '共享课堂' : '我的课程'} · {room.chapters.length} 个知识点</span>
      <h3>{room.title}</h3>
      <p className="sl-course-goal">{room.goal || '按知识点逐步学习，结合资料与练习加深理解。'}</p>
      <div className="sl-course-card-footer"><span>{shared ? `${resources.length} 份学习资料` : `已学完 ${completion(room)} / ${resources.length} 份资料`}</span><Icon name="arrow" size={16} /></div>
    </div>
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
  const currentChapter = resume?.chapters.find(c => c.resources.some(r => r.id === resume.selectedId)) || resume?.chapters[0];
  const currentResource = currentChapter?.resources.find(r => r.id === resume?.selectedId) || currentChapter?.resources[0];
  const resourceCount = resume ? allResources(resume).length : 0;
  const completedCount = resume ? completion(resume) : 0;
  const chapterIndex = resume?.chapters.findIndex(c => c.id === currentChapter?.id) ?? 0;
  function chooseStartingPoint(value: string) {
    setPrompt(value);
    promptRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    promptRef.current?.focus({ preventScroll: true });
  }
  return (
    <main className="sl-home sl-home-refresh">
      <section className="sl-home-hero">
        <div className="sl-learning-start">
        <div className="sl-home-identity"><Brand large /><span>你的 AI 学习空间</span></div>
        <h1>让好奇，成为你的下一堂课。</h1>
        <p className="sl-home-intro">带着问题来，沿着清晰的知识路径，学到真正理解。</p>
        <form className={`sl-prompt${preparationOptions ? ' sl-prompt-with-options' : ''}`} onSubmit={submit}>
          <div className="sl-composer-label"><Icon name="spark" size={17} /><span>今天，你想学会什么？</span></div>
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
            <span className="sl-composer-hint">告诉我目标和基础，或添加学习资料</span>
            <button
              className="sl-primary"
              disabled={!prompt.trim() && !canCreateFromUploads}
              type="submit"
            >
              开始学习 <Icon name="arrow" size={17} />
            </button>
          </div>
        </form>
        <div className="sl-learning-formats"><span><Icon name="book" size={15} />知识点讲解</span><span><Icon name="quiz" size={15} />练习巩固</span><span><Icon name="chat" size={15} />随时提问</span></div>
        </div>
        {resume ? <aside className="sl-home-companion" aria-label="继续上次学习">
          <div className="sl-companion-top"><span><Icon name="clock" size={15} />继续上次学习</span><span className="sl-companion-dot" /></div>
          <h2>{resume.title}</h2>
          <p className="sl-companion-description">接着上次的思路，再向前一步。</p>
          <div className="sl-resume-location"><small>当前学习位置</small><strong>{currentChapter?.title || '打开课程开始学习'}</strong>{currentResource && <span>{currentResource.title}</span>}</div>
          <div className="sl-resume-outline" aria-label="课程知识点预览">{resume.chapters.slice(Math.max(0, chapterIndex - 1), Math.max(0, chapterIndex - 1) + 3).map(c => <div key={c.id} className={c.id === currentChapter?.id ? 'current' : ''}><i /><span>{c.title}</span>{c.id === currentChapter?.id && <small>当前</small>}</div>)}</div>
          <div className="sl-resume-progress"><span>已标记学完 <b>{completedCount}</b> / {resourceCount} 份资料</span><progress aria-label="已标记学完的资料" value={completedCount} max={resourceCount || 1} /></div>
          <button className="sl-primary" onClick={() => onOpen(resume)}>继续学习<Icon name="arrow" size={17} /></button>
        </aside> : <aside className="sl-home-companion sl-home-onboarding" aria-label="如何开始学习">
          <div className="sl-companion-top"><span><Icon name="book" size={15} />从好奇到理解</span><span className="sl-companion-dot" /></div>
          <h2>一个想学的主题，<br />一条清晰的学习路径。</h2>
          <p className="sl-companion-description">从你的目标出发，把知识一点点串起来。</p>
          <ol>{[['spark', '说说想学什么', '告诉我你的目标、已有基础，也可以带上自己的资料。'], ['book', '沿着知识点学习', '结合讲解与学习资料，逐步理解一个主题。'], ['chat', '在练习和提问中理解', '遇到卡点随时问，用练习检查自己的理解。']].map(([icon, title, text]) => <li key={title}><Icon name={icon} size={20} /><div><strong>{title}</strong><p>{text}</p></div></li>)}</ol>
          <span className="sl-onboarding-note">从下方选一个方向，也可以写下自己的目标。</span>
        </aside>}
      </section>
      <section className="sl-starting-points" aria-label="学习方向示例">
        <div className="sl-starting-heading"><h2>从一个感兴趣的方向开始</h2><span>选择后可修改目标，再开始学习</span></div>
        <div className="sl-starting-grid">{startingPoints.map(point => <button key={point.title} className={`sl-starting-card ${point.tone}`} onClick={() => chooseStartingPoint(point.prompt)} aria-label={`试试：${point.title}`}><span className="sl-starting-icon"><Icon name={point.icon} size={21} /></span><span className="sl-starting-copy"><small>{point.tag}</small><strong>{point.title}</strong><span>{point.text}</span></span><Icon name="arrow" size={16} /></button>)}</div>
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
        每一次好奇，都值得认真探索。
        {!live && <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>}
      </footer>
    </main>
  );
}
