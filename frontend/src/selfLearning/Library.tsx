import { useEffect, useState } from "react";
import { allResources, kindLabel, type Classroom, type LearningResource } from "./model";
import { LearningContent, reportParagraphs } from "./Content";
import { Empty, Icon, Modal } from "./ui";
import { reviewEnabled, reviewWorkbenchHref } from "./review";

type Props = {
  resources: LearningResource[]; classroomId?: string; room?: Classroom; resourceId?: string;
  workbenchHref?: string;
  workbenchForResource?: (id: string) => string;
  onDownload?: (resource: LearningResource) => void | Promise<void>;
  onRename: (id: string, title: string) => void | Promise<void>; onRemove: (id: string) => void | Promise<void>;
  onPin?: (id: string) => void | Promise<void>; onAddToLearning?: (resource: LearningResource, chapterId: string) => void | Promise<void>;
};
export function ResourceCenter({ resources, classroomId, room, resourceId, workbenchHref, workbenchForResource, onDownload, onRename, onRemove, onPin, onAddToLearning }: Props) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(resources.some(r => r.id === resourceId && (!classroomId || !r.courseId || r.courseId === classroomId)) ? resourceId : undefined);
  const [chapter, setChapter] = useState("all");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [dialog, setDialog] = useState<"rename" | "remove" | "add" | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  async function perform(work: () => void | Promise<void>, done: () => void) {
    if (busy) return;
    setBusy(true); setFailure("");
    try { await work(); done(); } catch (e) { setFailure(e instanceof Error ? e.message : "保存失败，请重试"); }
    finally { setBusy(false); }
  }
  const [notice, setNotice] = useState("");
  const selectedChapter = room?.chapters.find(c => c.resources.some(r => r.id === room.selectedId));
  const [destination, setDestination] = useState(selectedChapter?.id || room?.chapters[0]?.id || "");
  const courseResources = room ? allResources(room) : [];
  const mine = resources.filter(r => !classroomId || !r.courseId || r.courseId === classroomId);
  const source = mine;
  const visible = source.filter(r =>
    (filter === "all" || r.kind === filter) && (!pinnedOnly || r.pinned) &&
    (chapter === "all" || r.chapterId === chapter) &&
    `${r.title} ${r.topic}`.toLowerCase().includes(query.trim().toLowerCase()),
  ).sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || b.createdAt - a.createdAt);
  const current = visible.find(r => r.id === selected) || visible[0];
  const attached = current && courseResources.find(r => r.id === current.id || r.sourceResourceId === current.id);
  const studioHref = current && workbenchForResource ? workbenchForResource(current.id) : reviewEnabled() && room && current ? reviewWorkbenchHref(room, current.id)
    : workbenchHref || (classroomId ? `#/studio?classroom=${classroomId}` : "#/studio");
  useEffect(() => { if (!notice) return; const timeout = setTimeout(() => setNotice(""), 3500); return () => clearTimeout(timeout); }, [notice]);
  function choose(id?: string) {
    setSelected(id); setDialog(null);
    const params = new URLSearchParams();
    if (classroomId) params.set("classroom", classroomId);
    if (id) params.set("resource", id);
    history.replaceState(null, "", `#/resources?${params}`);
  }
  function download(resource: LearningResource) {
    if (onDownload) { onDownload(resource); return; }
    const content = resource.content || `# ${resource.title}\n\n${reportParagraphs(resource).join("\n\n")}`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url;
    a.download = `${resource.title.replace(/[\\/:*?"<>|]/g, "-").slice(0, 60)}.md`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <main className={`sl-library ${selected ? "has-selection" : ""}`}>
    <aside className="sl-library-sidebar" aria-label="资源目录">
      <div className="sl-library-heading"><div><span className="sl-eyebrow">YOUR LEARNING LIBRARY</span><h1>资源中心</h1></div><span className="sl-count">{source.length}</span></div>
      <p className="sl-library-personal-caption">我的作品 · 保存个人生成的资源</p>
      <label className="sl-search-field"><Icon name="search" size={17} /><input aria-label="搜索资源" placeholder="搜索标题或知识点" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <div className="sl-library-types" aria-label="资源类型">{[["all", "全部"], ...Object.entries(kindLabel)].map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
      <div className="sl-library-filter-row"><select aria-label="按知识点筛选" value={chapter} onChange={e => setChapter(e.target.value)}><option value="all">全部知识点</option>{room?.chapters.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select>{<button className="sl-text-button" aria-pressed={pinnedOnly} onClick={() => setPinnedOnly(!pinnedOnly)}>仅置顶</button>}</div>
      <div className="sl-library-list">{visible.map(r => <button key={r.id} className={`sl-library-item ${current?.id === r.id ? "active" : ""}`} aria-pressed={current?.id === r.id} onClick={() => choose(r.id)}><span className={`sl-library-icon ${r.kind}`}><Icon name={r.kind} size={20} /></span><span><strong>{r.title}</strong><small>{kindLabel[r.kind]} · 第 {r.version || 1} 版{r.pinned ? " · 已置顶" : ""}</small></span><Icon name="chevron" size={14} /></button>)}
        {!visible.length && <p className="sl-inline-empty">{query || filter !== "all" || chapter !== "all" || pinnedOnly ? "没有匹配的资源，试试其他筛选条件。" : "这里还没有资源。"}</p>}
      </div>
      <a className="sl-library-create" href={studioHref}><Icon name="spark" size={18} /><span>去工作台创作<small>把想深入的问题，变成一份作品</small></span><Icon name="arrow" size={16} /></a>
    </aside>
    <section className="sl-library-detail" aria-label="资源预览">{current ? <>
      <header className="sl-library-detail-heading">
        <button className="sl-library-back sl-text-button" onClick={() => choose(undefined)}><Icon name="back" size={17} />资源列表</button>
        <div className="sl-library-title-row"><div><span className="sl-eyebrow">我的作品 / {kindLabel[current.kind]}</span><h2>{current.title}</h2><p>{room?.title || "个人资源"} · 第 {current.version || 1} 版 · {current.minutes} 分钟</p></div>{<button className="sl-icon-button" aria-label={current.pinned ? "取消置顶" : "置顶资源"} aria-pressed={!!current.pinned} onClick={() => onPin?.(current.id)}><Icon name="spark" size={18} /></button>}</div>
        <div className="sl-library-actions"><a className="sl-secondary-button" href={studioHref}><Icon name="chat" size={16} />引用到工作台</a>{<><button className="sl-text-button" onClick={() => { setName(current.title); setDialog("rename"); }}>重命名</button><button className="sl-text-button" onClick={() => setDialog("remove")}>删除资源</button></>}{current.kind === "report" && <button className="sl-text-button" onClick={() => download(current)}><Icon name="download" size={16} />下载 Markdown</button>}</div>
      </header>
      <div className="sl-library-preview"><LearningContent key={current.id} resource={current} /></div>
      <footer className="sl-library-footer"><span><Icon name={attached ? "check" : "book"} size={16} />{attached ? "已在学习目录中" : "将作品加入当前课程的学习目录"}</span>{attached && room ? <a className="sl-primary" href={`#/classroom/${room.id}?resource=${attached.id}`}>在课堂学习 <Icon name="arrow" size={16} /></a> : room ? <button className="sl-primary" onClick={() => setDialog("add")}>加入本节学习 <Icon name="arrow" size={16} /></button> : <a className="sl-primary" href="#/">选择课堂</a>}</footer>
    </> : <Empty title="为下一次理解，留一份好资料" text={source.length ? "选择资源即可阅读、引用或加入学习目录。" : "还没有个人作品，去工作台生成第一份资源吧。"} action={<a className="sl-primary" href={studioHref}>前往工作台</a>} />}</section>
    {dialog === "rename" && current && <Modal title="重命名资源" onClose={() => setDialog(null)}><form className="sl-library-dialog" onSubmit={e => { e.preventDefault(); if (name.trim()) { void perform(() => onRename(current.id, name.trim()), () => { setDialog(null); setNotice("名称已更新"); }); } }}><label className="sl-field">资源名称<input autoFocus aria-label="资源名称" maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label><button className="sl-primary" disabled={busy || !name.trim()}>保存名称</button></form></Modal>}
    {dialog === "remove" && current && <Modal title="删除这份作品？" onClose={() => setDialog(null)}><div className="sl-library-dialog"><p>删除“{current.title}”后，已加入课堂的学习副本和学习记录仍会保留。</p><div className="sl-modal-actions"><button className="sl-text-button" onClick={() => setDialog(null)}>保留</button><button className="sl-primary" onClick={() => { void perform(() => onRemove(current.id), () => choose(undefined)); }}>确认删除</button></div></div></Modal>}
    {dialog === "add" && current && room && <Modal title="加入学习目录" onClose={() => setDialog(null)}><div className="sl-library-dialog"><p>{current.title}</p><label className="sl-field">放在哪个知识点？<select aria-label="加入的知识点" value={destination} onChange={e => setDestination(e.target.value)}>{room.chapters.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><p className="sl-muted">保存为个人补充资料，保留作品原件。</p><button className="sl-primary" onClick={() => { void perform(() => onAddToLearning?.(current, destination), () => { setDialog(null); setNotice("已加入学习目录，可以回到课堂继续学习"); }); }}>确认加入</button></div></Modal>}
    {failure && <p className="sl-toast" role="alert">{failure}</p>}
    {notice && <div className="sl-toast" role="status"><Icon name="check" size={17} />{notice}</div>}
  </main>;
}
