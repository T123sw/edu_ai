import {useRecentOpens} from '../recent/context';
import {recentKey} from '../recent/store';
import { useState, type FormEvent, type ReactNode } from "react";
import { allResources, type Classroom } from "./model";
import { Brand, Icon } from "./ui";
import { ModuleIllustration } from "./ModuleIllustration";
import { moduleIdentity, type LearningModule } from "./moduleIdentity";

type Props = {
  rooms?: Classroom[];
  onCreate: (text: string) => void;
  onOpen?: (room: Classroom) => void;
  mode?: LearningModule;
  promptValue?: string;
  onPromptChange?: (value: string) => void;
  submitting?: boolean;
  createLabel?: string;
  createDisabled?: boolean;
  promptPlaceholder?: string;
  feedback?: ReactNode;
  resourceContent?: ReactNode;
  live?: boolean;
  canCreateFromUploads?: boolean;
  preparationOptions?: ReactNode;
  toolbar?: ReactNode;
  libraryTabs?: ReactNode;
  personalResourceContent?: ReactNode;
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

export function GeneratedResourceCard({ title, coverTitle = title, tone = "mint", label, detail, meta, onOpen }: { title: string; coverTitle?: string; tone?: Classroom["tone"]; label: string; detail: string; meta: string; onOpen: () => void }) {
  return <button className="sl-class-card" onClick={onOpen} title={title}>
    <div className={`sl-course-preview ${tone}`} aria-hidden="true">
      <span className="sl-jacket-spine" />
      <div className="sl-jacket-label"><span>EDU AI</span><span>{label}</span></div>
      <strong className="sl-jacket-title">{coverTitle}</strong>
      <svg className="sl-jacket-art" viewBox="0 0 160 100" fill="none"><ellipse cx="80" cy="51" rx="62" ry="27" transform="rotate(-28 80 51)" /><ellipse cx="80" cy="51" rx="62" ry="27" transform="rotate(28 80 51)" /><circle cx="80" cy="51" r="27" /><circle cx="130" cy="22" r="5" fill="currentColor" stroke="none" /></svg>
      <div className="sl-jacket-bottom"><span>{detail}</span><span>LEARN / EXPLORE</span></div>
    </div>
    <div className="sl-card-copy"><h3>{title}</h3><div className="sl-editorial-card-meta"><span>{meta}</span><Icon name="arrow" size={16} /></div></div>
  </button>;
}
function ClassroomCard({ room, onOpen }: { room: Classroom; onOpen: () => void }) {
  return <GeneratedResourceCard title={room.title} coverTitle={room.chapters[0]?.title || room.title} tone={room.tone} label="学习手记" detail={`${String(room.chapters.length).padStart(2, '0')} 个知识点`} meta={`${allResources(room).length} 份学习资料`} onOpen={onOpen} />;
}
export function Home({
  rooms = [],
  onCreate,
  onOpen = () => undefined,
  mode = "classroom",
  promptValue,
  onPromptChange,
  submitting = false,
  createLabel,
  createDisabled = mode === "exam",
  promptPlaceholder,
  feedback,
  resourceContent,
  live,
  canCreateFromUploads = false,
  preparationOptions,
  toolbar,
  libraryTabs,
  personalResourceContent,
}: Props) {
  const opened=useRecentOpens();
  const identity = moduleIdentity[mode];
  const [localPrompt, setLocalPrompt] = useState("");
  const prompt = promptValue ?? localPrompt;
  const setPrompt = onPromptChange ?? setLocalPrompt;
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const matches = (r: Classroom) =>
    `${r.title} ${r.goal}`.toLowerCase().includes(query.trim().toLowerCase());
  const canSubmit = !submitting && !createDisabled && (!!prompt.trim() || ((mode === "classroom" || mode === "exam") && canCreateFromUploads));
  function create() {
    if (canSubmit) onCreate(prompt.trim());
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    create();
  }
  const recent = opened.sort(rooms.filter(matches),r=>recentKey('classroom',r.id),(a,b)=>b.updatedAt-a.updatedAt);
  return (
    <main className="sl-home sl-home-editorial">
      {toolbar}
      {!live && <div className="sl-editorial-masthead"><Brand /><span>一处安静的学习空间</span></div>}
      <section className="sl-home-hero">
        <div className="sl-editorial-intro"><div className="sl-editorial-copy"><span className="sl-editorial-eyebrow"><i />{identity.eyebrow}</span><h1 aria-label={identity.first + identity.second}>{identity.first}<br /><em>{identity.second}</em></h1></div><ModuleIllustration mode={mode} /></div>
        <form className={`sl-prompt${preparationOptions ? ' sl-prompt-with-options' : ''}`} onSubmit={submit}>
          <div className="sl-editorial-composer-heading">
            <span><Icon name="spark" size={17} />今天，想探索什么？</span>
            <small>{mode === "practice" ? "想探索的现象 · 想验证的问题" : mode === "exam" ? "考试范围 · 题型 · 目标" : "目标 · 基础 · 想解决的问题"}</small>
          </div>
          <textarea
            aria-label={mode === "practice" ? "实验主题与目标" : mode === "exam" ? "考试范围与目标" : "学习知识点与目标"}
            placeholder={promptPlaceholder ?? (mode === "practice" ? "例如：改变摩擦系数和初速度，观察小车能滑多远" : mode === "exam" ? "- 我想检验 Python 基础知识\n- 重点考查变量、循环和函数\n- 希望通过模拟考试发现薄弱点" : "- 我想学习 Agent\n- 希望能独立做出一个 AI 助手\n- 会一点 Python，Agent 还是零基础")}
            disabled={mode === "exam" && submitting}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            maxLength={mode === "practice" ? 1800 : undefined}
            onKeyDown={(e) => {
              if (
                (e.ctrlKey || e.metaKey) &&
                e.key === "Enter" &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                create();
              }
            }}
          />
          <div className="sl-editorial-composer-toolbar"><div className="sl-creation-options">{preparationOptions}</div>
          <div className="sl-prompt-bottom">
            <button
              className="sl-primary"
              disabled={!canSubmit}
              type="submit"
            >
              {submitting ? "正在提交…" : createLabel ?? (mode === "practice" ? "生成互动实验" : mode === "exam" ? "即将上线" : "开始学习")} <Icon name="arrow" size={17} />
            </button>
          </div></div>
          {feedback}
        </form>
      </section>
      <div className="sl-home-library">
        {libraryTabs}
        {mode !== "classroom" ? resourceContent : personalResourceContent || <>
        <section aria-label="最近学习">
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
                <ClassroomCard key={r.id} room={r} onOpen={() => {opened.mark(recentKey('classroom',r.id));onOpen(r);}} />
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
        </>}
      </div>
      <footer className="sl-home-footer">
        <span className="sl-editorial-footer-mark">Edu AI <i>／</i> 学无止境</span><p>每一次好奇，都值得认真探索。</p>
        {!live && <span>本地交互演示 · 示例课堂与学习记录仅保存在此浏览器</span>}
      </footer>
    </main>
  );
}
