import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { CourseMaterial } from '../stitch/api/types';
import type { JobRecord } from '../jobs/types';
import { MarkdownPreview } from '../stitch/components/MarkdownPreview';
import { CourseMaterialArtifactPreview } from '../stitch/pages/CourseMaterialArtifactPreview';
import { Icon } from '../selfLearning/ui';

const sourceHost = (url: string) => { try { return new URL(url).hostname; } catch { return url; } };

type Source = { title: string; url: string; content: string };
type Research = { job: JobRecord; sources: Source[]; resource: (CourseMaterial & { studio_library_saved?: boolean }) | null };

export function ResearchReader({ jobId, onNew, onUpdated }: { jobId: string; onNew: () => void; onUpdated: () => void }) {
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<'answer' | 'sources'>('answer');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await apiRequest<Research>(`/api/personal-studio/research/${encodeURIComponent(jobId)}`);
        if (!live) return;
        setData(value); setError('');
        if (['queued', 'running', 'cancel_requested'].includes(value.job.status)) timer = setTimeout(poll, 2000);
      } catch { if (live) setError('暂时无法读取研究进展，请重试。'); }
    };
    void poll();
    return () => { live = false; clearTimeout(timer); };
  }, [jobId, retry]);
  async function collect() {
    if (!data?.resource || busy) return;
    setBusy(true);
    try {
      const resource = await apiRequest<Research['resource']>(`/api/personal-studio/resources/report/${encodeURIComponent(jobId)}/library`, { method: 'PUT', body: JSON.stringify({ saved: data.resource.studio_library_saved === false }) });
      setData(old => old ? { ...old, resource } : old); onUpdated(); setError('');
    } catch { setError('收藏未能更新，请重试。'); }
    finally { setBusy(false); }
  }
  const pending = data && ['queued', 'running', 'cancel_requested'].includes(data.job.status);
  const visibleTab = data?.resource ? tab : 'sources';
  return <section className="studio-research-reader" aria-label="研究阅读区">
    <div className="studio-research-meta"><span className="studio-eyebrow">{data?.resource ? '研究记录' : '正在探索'}</span><button className="studio-back" onClick={onNew}>研究新问题<Icon name="arrow" size={15} /></button></div>
    <div className="studio-research-heading"><h3>{String(data?.job.input_summary.title || '正在读取研究记录…')}</h3></div>
    {data && <p className="studio-research-context">{String(data.job.input_summary.studio_course_title || '研究记录')}{data.job.input_summary.studio_chapter_title ? ` / ${String(data.job.input_summary.studio_chapter_title)}` : ''}</p>}
    {error && <p className="studio-message" role="status">{error}<button onClick={() => setRetry(v => v + 1)}>重试</button></p>}
    {pending && <div className="studio-research-progress" role="status"><div><Icon name="spark" size={16} /><span>{data.job.message || '正在检索资料…'}</span><b>{data.job.progress}%</b></div><progress value={data.job.progress} max={100} /></div>}
    {data && !pending && !data.resource && <p className="studio-message">{data.job.status === 'canceled' ? '研究已取消，已取得的来源仍可阅读。' : '研究暂未完成，已取得的来源仍可阅读。可在后台任务中重试。'}</p>}
    {data && <div className="studio-reading-nav"><div role="tablist" aria-label="研究内容"><button role="tab" aria-selected={visibleTab === 'answer'} disabled={!data.resource} onClick={() => setTab('answer')}>研究结论</button><button role="tab" aria-selected={visibleTab === 'sources'} onClick={() => setTab('sources')}>参考资料 <span>{data.sources.length}</span></button></div>{data.resource && <button className="studio-collect" disabled={busy} onClick={() => void collect()}><Icon name="folder" size={14} />{data.resource.studio_library_saved === false ? '收藏研究结论' : '取消收藏'}</button>}</div>}
    {visibleTab === 'answer' && data?.resource && <div className="studio-research-answer"><CourseMaterialArtifactPreview material={data.resource} /></div>}
    {visibleTab === 'sources' && <div className="studio-research-sources">{!data?.sources.length ? <div className="studio-source-empty"><Icon name="search" size={28} /><p>正在寻找与问题相关的资料</p><span>来源就绪后会自动显示在这里</span></div> : <>{!data.resource && <p className="studio-hint">你可以先阅读来源，研究结论会在整理完成后呈现。</p>}{data.sources.map((source, index) => <details key={source.url}><summary><span className="studio-source-number">{String(index + 1).padStart(2, '0')}</span><span><strong>{source.title}</strong><small>{sourceHost(source.url)}</small></span><Icon name="arrow" size={15} /></summary><div className="studio-source-content"><a href={source.url} target="_blank" rel="noreferrer">查看原文 ↗</a><MarkdownPreview content={source.content} /></div></details>)}</>}</div>}
  </section>;
}
