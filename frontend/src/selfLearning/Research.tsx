import { useState, type FormEvent } from 'react';
import { uid, type Classroom } from './model';
import { Icon } from './ui';
import { parseResearchDrafts, researchSource, researchStorageKey, sourceHref, type ResearchDraft } from './research';

export function Research({ owner, rooms, query }: { owner: string; rooms: Classroom[]; query: URLSearchParams }) {
  const [stored] = useState(() => {
    try { return { drafts: parseResearchDrafts(localStorage.getItem(researchStorageKey(owner))), error: '' }; }
    catch (cause) { return { drafts: [], error: cause instanceof Error ? cause.message : '浏览器暂时无法读取草稿。' }; }
  });
  const [drafts, setDrafts] = useState(stored.drafts);
  const selected = drafts.find(d => d.id === query.get('draft'));
  const room = rooms.find(r => r.id === query.get('classroom'));
  const source = selected?.source || researchSource(room, query.get('resource') || undefined);
  const missingSource = !!query.get('classroom') && !source;
  const missingDraft = !!query.get('draft') && !selected;
  const [title, setTitle] = useState(selected?.title || (source ? `${source.chapterTitle} · 实践探索` : ''));
  const [question, setQuestion] = useState(selected?.question || '');
  const [outcome, setOutcome] = useState(selected?.outcome || '');
  const [notes, setNotes] = useState(selected?.notes || '');
  const [error, setError] = useState(stored.error);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const sourceRoom = source && rooms.find(r => r.id === source.courseId);
  const currentSource = sourceRoom && researchSource(sourceRoom, source?.resourceId);
  const versionChanged = source?.version !== undefined && currentSource?.version !== undefined && source.version !== currentSource.version;
  const disabled = !!stored.error || missingSource || missingDraft;

  function persist(next: ResearchDraft[]) {
    try { localStorage.setItem(researchStorageKey(owner), JSON.stringify(next)); setDrafts(next); setError(''); return true; }
    catch { setError('草稿未保存，浏览器存储可能不可用或空间不足。请保留当前内容后重试。'); return false; }
  }
  function save(e: FormEvent) {
    e.preventDefault();
    if (disabled || !title.trim() || !question.trim()) return;
    const draft: ResearchDraft = { id: selected?.id || uid(), title: title.trim(), question: question.trim(), outcome: outcome.trim(), notes: notes.trim(), source, updatedAt: Date.now() };
    if (persist([draft, ...drafts.filter(d => d.id !== draft.id)])) {
      if (selected) setSaved(true);
      else location.hash = `/research?${new URLSearchParams({ draft: draft.id })}`;
    }
  }
  return <main className="sl-module-page sl-research-page">
    <div className="sl-module-intro"><span className="sl-kicker">从理解，到亲手验证</span><h1>让学到的知识，有一个落点。</h1><p>从课程中的一个问题出发，记录你想验证的想法，准备自己的实践项目。</p></div>
    <section className="sl-research-journey" aria-label="课程与实践的衔接">
      {[["book", "课程学习", "理解概念，找到问题"], ["flask", "科研实践", "提出假设，设计验证"], ["folder", "积累成果", "记录结果，回到知识"]].map(([icon, name, text], i) => <div key={name}><span className="sl-journey-number">0{i + 1}</span><Icon name={icon} size={22} /><strong>{name}</strong><small>{text}</small></div>)}
    </section>
    <div className="sl-research-layout">
      <aside className="sl-research-list" aria-label="我的实践草稿"><div className="sl-section-heading"><h2>我的实践草稿 <span>{drafts.length}</span></h2><a href="#/research" className="sl-text-button">新建</a></div>
        <p>保存在当前浏览器，按账号区分。</p>
        {drafts.length ? drafts.map(d => <a key={d.id} href={`#/research?${new URLSearchParams({ draft: d.id })}`} className={d.id === selected?.id ? 'active' : ''} aria-current={d.id === selected?.id ? 'page' : undefined}><Icon name="report" size={18} /><span><strong>{d.title}</strong><small>{d.source?.chapterTitle || '独立探索'} · 草稿</small></span><Icon name="chevron" size={14} /></a>) : <div className="sl-research-empty"><Icon name="flask" size={28} /><strong>从一个好问题开始</strong><p>可以直接写下想法，也可以在课堂中选择“以本节发起实践”。</p></div>}
        <div className="sl-module-note"><Icon name="clock" size={19} /><div><strong>实验与导师功能筹备中</strong><p>现在可整理并保存项目草稿。实验运行、成果同步与科研 Agent 尚未开放。</p></div></div>
      </aside>
      <section className="sl-research-editor" aria-label="实践项目草稿">
        <div className="sl-section-heading"><h2>{selected ? '继续整理项目' : '准备一个实践项目'}</h2><span className="sl-state-label">项目草稿</span></div>
        {error && <p role="alert" className="sl-research-error">{error}</p>}
        {(missingSource || missingDraft) && <p role="alert" className="sl-research-error">{missingDraft ? '这个草稿不在当前账号的浏览器记录中。' : '来源课程或资料不可用，请回到课堂重新选择。'} <a href="#/research">新建独立草稿</a></p>}
        {source ? <div className="sl-research-source"><Icon name="book" /><div><small>来自课程 · {source.courseTitle}</small><strong>{source.chapterTitle}</strong><p>{source.resourceTitle}{source.version !== undefined ? ` · v${source.version}` : ''}</p>
          {currentSource ? <a href={sourceHref(source)}>回到{versionChanged ? '当前版' : '来源'}资料 <Icon name="arrow" size={14} /></a> : <small>来源暂不可访问，已保存的引用信息仍保留。</small>}
          {versionChanged && <small>课程资料已更新，草稿仍保留原版本引用。</small>}
        </div></div> : <div className="sl-research-source"><Icon name="flask" /><div><strong>独立探索</strong><p>也可以从课堂当前知识点发起，自动带入来源资料引用。</p><a href="#/">选择一堂课 <Icon name="arrow" size={14} /></a></div></div>}
        <form onSubmit={save} onChange={() => setSaved(false)}>
          <label>项目名称<input required maxLength={120} value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：模型越复杂，预测就越准确吗？" /></label>
          <label>我想研究的问题<textarea required maxLength={3000} rows={3} value={question} onChange={e => setQuestion(e.target.value)} placeholder="想验证什么？哪些现象让你产生了疑问？" /></label>
          <label>希望得到的成果 <small>选填</small><input maxLength={500} value={outcome} onChange={e => setOutcome(e.target.value)} placeholder="例如：一组对照实验，以及有证据支持的结论" /></label>
          <label>已有想法与准备 <small>选填</small><textarea maxLength={6000} rows={4} value={notes} onChange={e => setNotes(e.target.value)} placeholder="记录假设、可能使用的数据，或需要补充的知识。" /></label>
          <div className="sl-research-save"><button className="sl-primary" disabled={disabled || !title.trim() || !question.trim()} type="submit"><Icon name="check" size={17} />保存项目草稿</button><span role="status">{saved ? '已保存到当前浏览器' : '保存草稿不会启动实验或生成任务'}</span></div>
        </form>
        {selected && <div className="sl-research-delete">{deleting ? <><span>删除当前草稿？课程内容不会改变。</span><button onClick={() => { if (persist(drafts.filter(d => d.id !== selected.id))) location.hash = '/research'; }}>确认删除</button><button onClick={() => setDeleting(false)}>取消</button></> : <button onClick={() => setDeleting(true)}>删除草稿</button>}</div>}
      </section>
    </div>
  </main>;
}
