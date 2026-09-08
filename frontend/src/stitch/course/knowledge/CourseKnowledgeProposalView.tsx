import { useState } from 'react';
import type { CourseKnowledgeProposal, KnowledgeGraphNode } from '../../api/types';

function Outline({ root, depth = 0 }: { root: KnowledgeGraphNode; depth?: number }) {
  return <ul>{(root.children || []).map(node => <li key={node.id}>{node.children?.length
    ? <details open={depth < 2}><summary>{node.label}</summary><Outline root={node} depth={depth + 1} /></details>
    : <span title={String(node.data?.summary || '')}>{node.label}</span>}</li>)}</ul>;
}
export function CourseKnowledgeProposalView({ proposal, busy, onSelect, onBack }: {
  proposal: CourseKnowledgeProposal; busy: boolean;
  onSelect: (selection: { option_id?: string; item_ids?: string[] }) => void; onBack: () => void;
}) {
  const [selected, setSelected] = useState<string[]>(proposal.items.map(item => item.id));
  const names = { brief: '简明', standard: '标准', complete: '完整' };
  return <section className="course-kb-proposal">
    <h3>{proposal.mode === 'create' ? '比较课程大纲' : '确认本次补充内容'}</h3>
    <p>{proposal.summary}</p>
    {proposal.mode === 'create' ? <div className="course-kb-proposal__options">{proposal.options.map(option =>
      <article key={option.id}>
        <h4>{names[option.level]}</h4><p>{option.description}</p>
        <small>{option.metrics.leaf_count} 个知识点</small>
        <Outline root={option.root} />
        <button disabled={busy} className="course-kb-wizard__primary" onClick={() => onSelect({ option_id: option.id })}>选择{names[option.level]}大纲</button>
      </article>)}</div>
      : <div className="course-kb-proposal__items">{proposal.items.length ? proposal.items.map(item => <label key={item.id}>
        <input type="checkbox" disabled={busy} checked={selected.includes(item.id)} onChange={event => setSelected(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
        <span><strong>{item.kind === 'add_node' ? '新增知识点：' : '补充资料：'}{item.title}</strong><p>{item.reason}</p>
          {item.materials.length > 0 && <small>{item.materials.join(' · ')}</small>}
          {item.evidence_document_ids.length > 0 && <small>参考资料：{item.evidence_document_ids.map(id => proposal.document_snapshot?.find(d => d.id === id)?.name || '课程资料').join('、')}</small>}
        </span>
      </label>) : <p>当前没有明确需要补充的内容，可以返回说明更具体的需求。</p>}</div>}
    <div className="course-kb-wizard__footer is-split"><button disabled={busy} onClick={onBack}>修改需求</button>
      {proposal.mode === 'supplement' && <button className="course-kb-wizard__primary" disabled={busy || !selected.length} onClick={() => onSelect({ item_ids: selected })}>检查目录并继续（{selected.length} 项）</button>}
    </div>
  </section>;
}
