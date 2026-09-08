import { create } from 'zustand';
import { useEffect, useRef } from 'react';
import type { ArtifactRevisionOutcome, ArtifactDraftAction } from '../../services/teacher/chatV2';
import { MarkdownPreview } from '../components/MarkdownPreview';
import './draftPreview.css';

type Entry = { owner: string; courseId: string; conversationId: string; outcome: ArtifactRevisionOutcome; busy: boolean };
export const useDraftPreview = create<{ entry: Entry | null; setEntry: (entry: Entry | null) => void }>(set => ({
  entry: null, setEntry: entry => set({ entry }),
}));
const listeners = new Set<(action: ArtifactDraftAction) => void>();
export function subscribeDraftAction(listener: (action: ArtifactDraftAction) => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function DraftDocumentPreview({ draft, busy }: { draft: NonNullable<ArtifactRevisionOutcome['draft']>; busy: boolean }) {
  const root = useRef<HTMLElement>(null);
  useEffect(() => {
    const pane = root.current?.closest<HTMLElement>('.generation-factory__preview-body');
    const target = root.current?.querySelector<HTMLElement>('[data-change="focus"], [data-change="delete"], [data-change="insert"]');
    if (pane && target) {
      const top = target.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 120;
      // Scroll only the document pane; keep the conversation at its current position.
      if (top > pane.clientHeight / 2) pane.scrollTo({ top: Math.max(0, top) });
    }
  }, [draft.draft_id, draft.revision]);
  const act = (action: ArtifactDraftAction['action']) => {
    if (!busy) for (const listener of listeners) listener({ action, draft_id: draft.draft_id, revision: draft.revision });
  };
  return <section ref={root} className="revision-draft" aria-label="文档修改稿">
    <div className="revision-draft__toolbar">
      <span>修改稿 · 尚未保存</span>
      <button type="button" disabled={busy} onClick={() => act('discard')}>放弃修改</button>
      <button type="button" disabled={busy} onClick={() => act('save')}>保存修改</button>
    </div>
    <div className="revision-draft__legend" aria-label="修改标记说明">
      <span className="is-focus">黄色：定位范围</span><del className="is-delete">红色：拟删除</del><ins className="is-insert">蓝色：拟新增</ins>
    </div>
    <p className="revision-draft__focus">定位：{draft.focus}</p>
    <div className="revision-draft__document">
      {draft.segments.map((segment, index) => {
        const content = <MarkdownPreview content={segment.text} />;
        return <div key={index} className={`revision-draft__block is-${segment.kind}`} data-change={segment.kind}>
          {segment.kind === 'delete' ? <del aria-label="拟删除内容">{content}</del> : segment.kind === 'insert' ? <ins aria-label="拟新增内容">{content}</ins> : content}
        </div>;
      })}
    </div>
  </section>;
}
