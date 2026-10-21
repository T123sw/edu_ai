import { useId, useLayoutEffect, useRef, useState } from 'react';
import { MarkdownPreview } from '../../stitch/components/MarkdownPreview';
import { reviewCard, startRound, type StudyCard } from './round';
import './flashcards.css';

function ReviewIcon({ check = false }: { check?: boolean }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {check ? <path d="m5 12 4 4L19 6" /> : <path d="M4 10a8 8 0 1 1 1 8M4 4v6h6" />}
  </svg>;
}

export function FlashcardRound({ cards }: { cards: StudyCard[] }) {
  const [round, setRound] = useState(() => startRound(cards.length));
  const [revealed, setRevealed] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const completeRef = useRef<HTMLHeadingElement>(null);
  const restoreFocus = useRef(false);
  const cardId = useId();
  const cardIndex = round.remaining[0];
  const card = cards[cardIndex];

  useLayoutEffect(() => {
    if (restoreFocus.current) {
      (cardRef.current ?? completeRef.current)?.focus({ preventScroll: true });
      restoreFocus.current = false;
    }
  }, [round]);

  const restart = () => {
    restoreFocus.current = true;
    setRound(startRound(cards.length));
    setRevealed(false);
  };
  const mark = (known: boolean) => {
    if (!revealed) return;
    restoreFocus.current = true;
    setRound(previous => reviewCard(previous, known));
    setRevealed(false);
  };

  if (!cards.length) return <p>当前闪卡暂无可练习的内容。</p>;
  return <section className="flashcard-round" aria-label="本轮闪卡练习">
    <header className="flashcard-round-progress">
      <div className="flashcard-round-progress-top">
        <span className="flashcard-round-eyebrow">本轮记忆</span>
        <span className="flashcard-round-remaining">{round.remaining.length ? <>还剩 <strong>{round.remaining.length}</strong> 张</> : '全部掌握'}</span>
      </div>
      <div className="flashcard-round-count" role="status" aria-atomic="true">
        <strong>{round.known}</strong><span>/ {cards.length}</span><span className="flashcard-round-count-label">张已掌握</span>
      </div>
      <progress value={round.known} max={cards.length} aria-label="本轮掌握进度" />
    </header>
    {card ? <>
      <div className="flashcard-round-stack">
        <div
          key={round.attempts}
          ref={cardRef}
          className={`flashcard-round-card${revealed ? ' is-flipped' : ''}`}
          role="button"
          tabIndex={0}
          aria-label={revealed ? '翻回问题' : '翻转卡片'}
          aria-describedby={`${cardId}-${revealed ? 'back' : 'front'}`}
          aria-pressed={revealed}
          onClick={event => {
            const control = (event.target as Element).closest('a, button, input, summary, [role="region"]');
            if (control && event.currentTarget.contains(control)) return;
            const selection = window.getSelection();
            if (selection?.toString() && event.currentTarget.contains(selection.anchorNode)) return;
            setRevealed(previous => !previous);
          }}
          onKeyDown={event => {
            if (event.target !== event.currentTarget || event.repeat) return;
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setRevealed(previous => !previous);
            }
          }}
        >
          <div className="flashcard-round-flipper">
            <div className="flashcard-round-face flashcard-round-front" aria-hidden={revealed} {...(revealed ? { inert: '' } : {})}>
              <div className="flashcard-round-face-top"><span>回忆一下</span><span>{String(cardIndex + 1).padStart(2, '0')} / {String(cards.length).padStart(2, '0')}</span></div>
              <div id={`${cardId}-front`} className="flashcard-round-content edu-rich-preview"><MarkdownPreview content={card.front} /></div>
              <div className="flashcard-round-flip-hint"><ReviewIcon /><span>想好了吗？点击卡片翻面</span></div>
            </div>
            <div className="flashcard-round-face flashcard-round-back" aria-hidden={!revealed} {...(!revealed ? { inert: '' } : {})}>
              <div className="flashcard-round-face-top"><span>参考答案</span><span>{String(cardIndex + 1).padStart(2, '0')} / {String(cards.length).padStart(2, '0')}</span></div>
              <div id={`${cardId}-back`} className="flashcard-round-content edu-rich-preview"><MarkdownPreview content={card.back} /></div>
              {card.source_title && <p className="flashcard-round-source">资料来源：{card.source_title}</p>}
              <div className="flashcard-round-flip-hint"><ReviewIcon /><span>点击卡片，回看问题</span></div>
            </div>
          </div>
        </div>
      </div>
      <div className="flashcard-round-footer">
        {revealed ? <div className="flashcard-round-actions">
          <button type="button" className="flashcard-round-retry" onClick={() => mark(false)}><ReviewIcon />再练一次</button>
          <button type="button" className="flashcard-round-known" onClick={() => mark(true)}><ReviewIcon check />已经掌握</button>
        </div> : <p className="flashcard-round-prompt">先在心里回答，再翻面核对</p>}
        {revealed && <p className="flashcard-round-hint">还不熟的卡片会在本轮稍后再次出现</p>}
      </div>
    </> : <div className="flashcard-round-complete" role="status">
      <span className="flashcard-round-complete-icon"><ReviewIcon check /></span>
      <h3 ref={completeRef} tabIndex={-1}>本轮完成</h3>
      <p>{cards.length} 张卡片全部掌握，共回忆 {round.attempts} 次。</p>
      <button type="button" onClick={restart}><ReviewIcon />再练一轮</button>
    </div>}
  </section>;
}
