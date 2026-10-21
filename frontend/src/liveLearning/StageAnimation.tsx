import { Icon } from '../selfLearning/ui';

export function StageAnimation({ stage, done, stopped }: { stage: string; done: boolean; stopped: boolean }) {
  const kind = done ? 'done' : stopped ? 'stopped' : ['normalize', 'ingest'].includes(stage) ? 'scan'
    : stage === 'research_scope' || stage === 'research_nodes' ? 'search'
    : stage === 'plan' ? 'plan' : ['review', 'repair'].includes(stage) ? 'review'
    : stage === 'commit' ? 'save' : stage === 'produce' ? 'produce' : 'waiting';
  return <div className={`sl-prep-art art-${kind}`} aria-hidden="true">
    <div className="sl-prep-orbit" /><span className="sl-prep-star star-one">✦</span><span className="sl-prep-star star-two">✦</span>
    {done || stopped ? <div className="sl-prep-result-icon"><Icon name={done ? 'check' : 'pause'} size={48} /></div>
      : <>
        <div className="sl-prep-sheet sheet-back"><Icon name="book" size={22} /></div>
        <div className="sl-prep-sheet sheet-front">
          <div className="sl-prep-sheet-heading"><span /><i /><i /><i /></div>
          {kind === 'produce' ? <><div className="sl-prep-slide"><Icon name="play" size={24} /><span /><span /></div><div className="sl-prep-lines"><i /><i /></div></>
            : <div className="sl-prep-lines">{[0, 1, 2, 3].map(n => <div key={n}><b>{kind === 'review' ? '✓' : kind === 'plan' ? n + 1 : ''}</b><i /><i /></div>)}</div>}
          <div className="sl-prep-scan" />
        </div>
        <span className="sl-prep-floating-icon"><Icon name={kind === 'search' ? 'search' : kind === 'save' ? 'check' : kind === 'produce' ? 'quiz' : 'spark'} size={27} /></span>
      </>}
  </div>;
}
