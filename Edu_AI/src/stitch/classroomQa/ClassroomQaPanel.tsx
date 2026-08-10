import { useEffect, useRef, useState } from 'react';
import { MaterialIcon } from '../shared';
import { toClassroomQaPresentation } from './classroomQaPresentation';
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
  const [question, setQuestion] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const historyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (state.isOpen && state.phase === 'drafting') {
      textareaRef.current?.focus();
    }
  }, [state.isOpen, state.phase]);

  useEffect(() => {
    historyRef.current?.scrollTo({
      top: historyRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [state.turns.length]);

  const submit = () => {
    const normalized = question.trim();
    if (!presentation.canSubmit || !normalized) return;
    setQuestion('');
    void controller.submitQuestion(normalized);
  };

  return (
    <>
      {!state.isOpen ? (
        <button
          type="button"
          className="classroom-qa-entry"
          onClick={controller.openQuestion}
          disabled={!canAsk}
          aria-label="打开课堂实时问答"
          title={canAsk ? '暂停课堂并提问' : '播放课堂后即可提问'}
        >
          <MaterialIcon name="forum" />
          <span>提问</span>
        </button>
      ) : null}

      {state.isOpen ? (
        <aside
          className="classroom-qa-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="classroom-qa-title"
        >
          <header className="classroom-qa-panel__header">
            <div>
              <p className="classroom-qa-panel__eyebrow">随时打断 · 回答后续讲</p>
              <h2 id="classroom-qa-title">课堂实时问答</h2>
            </div>
            <button
              type="button"
              onClick={controller.closePanel}
              aria-label="关闭问答面板"
              className="classroom-qa-icon-button"
            >
              <MaterialIcon name="close" />
            </button>
          </header>

          <div ref={historyRef} className="classroom-qa-history" aria-label="问答记录">
            {state.turns.length ? (
              state.turns.map((turn) => (
                <article key={turn.turn_id} className="classroom-qa-turn">
                  <div className="classroom-qa-turn__question">
                    <span>你</span>
                    <p>{turn.question}</p>
                  </div>
                  <div className="classroom-qa-turn__answer">
                    <span>AI</span>
                    <div>
                      <p>{turn.answer_text}</p>
                      <small>{turn.transition_text}</small>
                    </div>
                  </div>
                </article>
              ))
            ) : (
              <div className="classroom-qa-empty">
                <MaterialIcon name="lightbulb" />
                <p>可以针对当前讲授内容输入问题，AI 回答后会自然继续授课。</p>
              </div>
            )}
          </div>

          <div className="classroom-qa-status" aria-live="polite" role="status">
            <span className={`is-${state.phase}`} aria-hidden="true" />
            {presentation.statusText}
          </div>

          <div className="classroom-qa-composer">
            <textarea
              ref={textareaRef}
              value={question}
              maxLength={1000}
              rows={3}
              disabled={!presentation.canSubmit}
              placeholder="输入你对当前内容的问题…"
              aria-label="课堂问题"
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && state.phase === 'drafting') {
                  event.preventDefault();
                  controller.cancelDraft();
                }
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                  event.preventDefault();
                  submit();
                }
              }}
            />
            <div className="classroom-qa-composer__meta">
              <span>{question.length}/1000</span>
              {state.phase === 'drafting' ? (
                <div>
                  <button type="button" onClick={controller.cancelDraft}>
                    取消提问
                  </button>
                  <button
                    type="button"
                    className="is-primary"
                    onClick={submit}
                    disabled={!question.trim()}
                  >
                    发送
                  </button>
                </div>
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
      ) : null}
    </>
  );
}
