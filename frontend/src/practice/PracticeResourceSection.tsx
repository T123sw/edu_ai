import {useRecentOpens} from '../recent/context';
import {recentKey} from '../recent/store';
import { useState } from 'react';
import { GeneratedResourceCard } from '../selfLearning/Home';
import { Icon } from '../selfLearning/ui';

const statuses: Record<string, string> = { queued: '等待生成', running: '正在生成', ready: '可以体验', succeeded: '可以体验', failed: '生成失败', canceled: '已取消', cancel_requested: '取消中', partially_succeeded: '尚未完成' };
type Item = { id: string; topic: string; status: string };
export function PracticeResourceSection({ kind, items, loading, loadFailed, onRefresh, onOpen }: {
  kind: '实验' | '项目'; items: Item[]; loading: boolean; loadFailed: boolean;
  onRefresh: () => void; onOpen: (id: string) => void;
}) {
  const recent=useRecentOpens();
  const key=(item:Item)=>recentKey(kind==='项目'?'project':'practice',item.id);
  const [search, setSearch] = useState(false);
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState(false);
  const ready = (status: string) => ['ready', 'succeeded'].includes(status);
  const matches = recent.sort(items,key).filter(item => item.topic.toLowerCase().includes(query.trim().toLowerCase()));
  return <section aria-label={`我的${kind}`}>
    <div className="sl-section-heading"><h2><Icon name="clock" size={18} />我的{kind} <span>{items.length}</span></h2>
      <div className="sl-inline">{search && <input className="sl-small-input" aria-label={`搜索${kind}`} placeholder={`搜索${kind}…`} autoFocus value={query} onChange={e => setQuery(e.target.value)} />}
        <button className="sl-icon-button" aria-label={search ? `关闭${kind}搜索` : `搜索${kind}`} onClick={() => { setSearch(!search); setQuery(''); }}><Icon name={search ? 'close' : 'search'} size={18} /></button>
        {matches.length > 4 && <button className="sl-text-button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? '收起' : '查看全部'}</button>}
      </div>
    </div>
    {loading ? <p className="sl-inline-empty" role="status">正在读取{kind}…</p> : loadFailed ? <p className="sl-inline-empty">暂时无法读取{kind}。<button className="sl-text-button" onClick={onRefresh}>重新加载</button></p> : matches.length ? <div className="sl-card-grid">{matches.slice(0, expanded ? undefined : 4).map(item => <GeneratedResourceCard key={item.id} title={item.topic} label={kind === '项目' ? '编程项目' : '互动实验'} detail={statuses[item.status] || '处理中'} meta={ready(item.status) ? (kind === '项目' ? '打开项目，继续实现' : '打开实验，继续探索') : '查看生成进度'} onOpen={() => {recent.mark(key(item));onOpen(item.id);}} />)}</div> : <p className="sl-inline-empty">{query ? `暂无匹配的${kind}。` : kind === '项目' ? '还没有项目，选择上方的编程练习（PBL）开始创建。' : '还没有实验，从上面的输入框开始第一次探索。'}</p>}
  </section>;
}
