import { useEffect, useRef, useState } from 'react';
import { MaterialIcon } from '../shared';
import { toClassroomQaPresentation } from './classroomQaPresentation';
import { selectVisibleTurns } from './classroomQaState';
import type { ClassroomInterruptionController } from './useClassroomInterruption';

export function ClassroomQaPanel({
  controller,
  canAsk,
}: {
  controller: ClassroomInterruptionController;
  canAsk: boolean;
}) {
  const { state } = controller;
  const presentation = toClassroomQaPresentation(state);
  const visibleTurns = selectVisibleTurns(state);
  const [question, setQuestion] = useState('');
  const historyRef = useRef<HTMLDivElement | null>(null);
  const shouldStickToBottomRef = useRef(true);

  useEffect(() => {
    const history = historyRef.current;
    if (!history || !shouldStickToBottomRef.current) return;
    history.scrollTo({ top: history.scrollHeight, behavior: 'smooth' });
  }, [state.phase, visibleTurns.length]);

  const submit = () => {
    const normalized = question.trim();
    if (!canAsk || !presentation.canSubmit || !normalized) return;
    const pending = controller.submitQuestion(normalized);
    if (controller.state.activeTurn?.question === normalized) setQuestion('');
    void pending;
  };

  const statusText =
    state.phase === 'ready' && !canAsk
      ? '播放课堂后即可发送问题。'
      : presentation.statusText;

  return (
    <aside className="classroom-qa-panel" aria-label="课堂实时问答">
      <header className="classroom-qa-panel__header">
        <div>
          <p className="classroom-qa-panel__eyebrow">随时提问 · 回答后续讲</p>
          <h2>课堂实时问答</h2>
        </div>
      </header>

      <div
        ref={historyRef}
        className="classroom-qa-history"
        aria-label="问答记录"
        role="log"
        aria-live="polite"
        onScroll={(event) => {
          const element = event.currentTarget;
          shouldStickToBottomRef.current =
            element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}
      >
        {visibleTurns.length ? (
          visibleTurns.map((visibleTurn) => (
            <article
              key={visibleTurn.clientTurnId}
              className="classroom-qa-turn"
              data-status={visibleTurn.status}
            >
              <div className="classroom-qa-turn__question">
                <p>{visibleTurn.question}</p>
                <span aria-label="学生">你</span>
              </div>
              <div className="classroom-qa-turn__answer">
                <span aria-label="AI 教师">AI</span>
                {visibleTurn.turn ? (
                  <div>
                    <p>{visibleTurn.turn.answer_text}</p>
                    <small>{visibleTurn.turn.transition_text}</small>
                  </div>
                ) : (
                  <div className="classroom-qa-turn__pending">
                    <p>
                      {visibleTurn.status === 'error'
                        ? state.error || '回答失败，请重试。'
                        : '正在结合当前讲解回答…'}
                    </p>
                  </div>
                )}
              </div>
            </article>
          ))
        ) : (
          <div className="classroom-qa-empty">
            <MaterialIcon name="lightbulb" />
            <p>可以针对当前讲授内容输入问题，发送时课堂会暂停，回答后自然继续。</p>
          </div>
        )}
      </div>

      <div className="classroom-qa-status" aria-live="polite" role="status">
        <span className={`is-${state.phase}`} aria-hidden="true" />
        {statusText}
      </div>

      <div className="classroom-qa-composer">
        <textarea
          value={question}
          maxLength={1000}
          rows={3}
          disabled={presentation.isBusy}
          placeholder="输入你对当前内容的问题…"
          aria-label="课堂问题"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
              event.preventDefault();
              submit();
            }
          }}
        />
        <div className="classroom-qa-composer__meta">
          <span>{question.length}/1000</span>
          {state.phase === 'ready' ? (
            <button
              type="button"
              className="is-primary"
              onClick={submit}
              disabled={!canAsk || !question.trim()}
            >
              发送
            </button>
          ) : null}
          {presentation.isBusy ? (
            <button
              type="button"
              className="is-danger"
              onClick={controller.stopAnswerAndResume}
            >
              停止回答并继续授课
            </button>
          ) : null}
          {state.phase === 'error' ? (
            <div>
              <button type="button" onClick={controller.stopAnswerAndResume}>
                放弃并继续授课
              </button>
              <button
                type="button"
                className="is-primary"
                onClick={() => void controller.retry()}
              >
                重试
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
