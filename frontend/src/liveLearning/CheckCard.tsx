import { ChoiceOptions } from './ChoiceOptions';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { PracticeContext } from './readingContext';
import { QuizMarkdown } from './QuizMarkdown';
import { quizTypeLabel } from './quizPresentation';

type Attempt = { attempt_id: string; status: string; option_ids: string[]; text: string; correct: boolean | null; feedback: string; evaluator: string | null };
type Teaching = { enabled: boolean; revision: number; feedback?: { status: string; turn_id?: string; error?: string } | null };
export type Check = { check_id: string; question_version: number; source_available?: boolean; teaching?: Teaching | null; public_question: { form: 'choice' | 'short_answer'; stem: string; options: { id: string; text: string }[] }; attempts?: Attempt[] };
export function CheckCard({ course, topic, owner, refreshKey, checkId, initialCheck, questionType, onReference, onSavedAttempt, questionNumber }: { course: string; topic: string; owner: string; refreshKey?: string; checkId?: string; initialCheck?: Check; questionType?: string; onReference?: (practice: PracticeContext, prompt?: string) => void; onSavedAttempt?: (practice: PracticeContext) => void; questionNumber?: number }) {
  const [checks, setChecks] = useState<Check[]>(() => initialCheck && initialCheck.check_id === checkId ? [initialCheck] : []);
  const [choice, setChoice] = useState<string[]>([]);
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const path = `/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/checks`;
  const authorized = useCallback(() => { try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === owner; } catch { return false; } }, [owner]);
  const refresh = useCallback(async () => {
    if (!authorized()) return;
    const result = checkId ? { items: [await apiRequest<Check>(`/api/self-learning/checks/${encodeURIComponent(checkId)}`)] } : await apiRequest<{ items: Check[] }>(path);
    if (alive.current && authorized()) setChecks(result.items);
  }, [path, authorized, checkId]);
  useEffect(() => {
    alive.current = true;
    // The material checks endpoint already returns questions, saved attempts and teaching state.
    if (initialCheck && initialCheck.check_id === checkId && authorized()) setChecks([initialCheck]);
    else void refresh().catch(e => { if (alive.current) setError(e.message); });
    return () => { alive.current = false; };
  }, [refresh, refreshKey, initialCheck, checkId, authorized]);
  const check = checks[0];
  const latestAttempt = check?.attempts?.[0];
  const attempt = questionNumber && latestAttempt?.status === 'skipped' ? undefined : latestAttempt;
  const singleChoice = questionType === 'single_choice' || questionType === 'true_false';
  const judgment = questionType === 'true_false' && check?.public_question.form === 'short_answer';
  const draftKey = check ? `learning-check-draft:${owner}:${check.check_id}` : undefined;
  useEffect(() => {
    if (!draftKey || !authorized()) return;
    setChoice([]); setAnswer('');
    try {
      const saved = JSON.parse(localStorage.getItem(draftKey) || 'null');
      if (saved && Array.isArray(saved.options) && typeof saved.text === 'string') {
        setChoice(saved.options); setAnswer(saved.text);
      }
    } catch { /* a malformed local draft never becomes a submitted answer */ }
  }, [draftKey, authorized]);
  function saveDraft(options: string[], text: string) {
    setChoice(options); setAnswer(text);
    if (draftKey && authorized()) localStorage.setItem(draftKey, JSON.stringify({ options, text }));
  }
  function reference(prompt?: string) {
    if (!check || !authorized()) return;
    onReference?.({ check_id: check.check_id, ...(attempt ? { attempt_id: attempt.attempt_id } : { draft: { option_ids: choice, text: answer } }) }, prompt);
  }
  async function run(action: () => Promise<unknown>) {
    if (busy || !authorized()) return;
    setBusy(true); setError('');
    try { await action(); await refresh(); } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : '保存失败'); }
    finally { if (alive.current) setBusy(false); }
  }
  async function offer() {
    const key = `learning-check-offer:${owner}:${course}:${topic}`;
    const request = localStorage.getItem(key) || JSON.stringify({ request_id: crypto.randomUUID(), preferred_form: 'choice', objective_ids: [] });
    localStorage.setItem(key, request);
    await apiRequest(path, { method: 'POST', body: request });
    localStorage.removeItem(key); setChoice([]); setAnswer('');
  }
  async function submit(skipped = false) {
    if (!check) return;
    const key = `learning-check-submit:${owner}:${check.check_id}`;
    const content = { question_version: check.question_version, skipped, option_ids: skipped ? [] : choice, text: skipped ? '' : answer };
    let old: { content: string; body: string } | null = null;
    try { old = JSON.parse(localStorage.getItem(key) || 'null'); } catch { /* malformed pending data is replaced */ }
    const pending = old?.content === JSON.stringify(content) ? old : { content: JSON.stringify(content), body: JSON.stringify({ request_id: crypto.randomUUID(), ...content }) };
    localStorage.setItem(key, JSON.stringify(pending));
    // The removed automatic-coaching option must not keep firing for earlier opt-ins.
    if (questionNumber && check.teaching?.enabled) {
      await apiRequest(`/api/self-learning/checks/${encodeURIComponent(check.check_id)}/teaching`, { method: 'PUT', body: JSON.stringify({ enabled: false, expected_revision: check.teaching.revision }) });
    }
    const saved = await apiRequest<Attempt>(`/api/self-learning/checks/${encodeURIComponent(check.check_id)}/attempts`, { method: 'POST', body: pending.body });
    if (alive.current && authorized()) onSavedAttempt?.({ check_id: check.check_id, attempt_id: saved.attempt_id });
    localStorage.removeItem(key);
    if (draftKey) localStorage.removeItem(draftKey);
  }
  return <section className="sl-check-card quiz-question-card" aria-label="理解检查">
    <div className="quiz-question-heading"><strong>{questionNumber ? `第 ${questionNumber} 题` : '检查一下理解'}</strong>{questionType && <span className="quiz-type-tag">{quizTypeLabel(questionType)}</span>}{attempt?.status === 'graded' && <span className={`quiz-result-tag ${attempt.correct ? 'is-correct' : 'is-incorrect'}`}>{attempt.evaluator === 'model' ? attempt.correct ? '要点符合' : '待补充' : attempt.correct ? '回答正确' : '回答有误'}</span>}</div>{!questionNumber && <small>可以跳过；单题结果不代表掌握整个知识点。</small>}
    {check && <>
      <QuizMarkdown content={check.public_question.stem} />{check.source_available === false && <p>原资料版本暂不可用，以下保留的是已保存题目和作答；不适用于新版资料。</p>}
      {!attempt ? <>
        <ChoiceOptions name={check.check_id} options={check.public_question.options} selected={choice} multiple={!singleChoice} disabled={busy || check.source_available === false} onChange={options => saveDraft(options, answer)} />
        {judgment && ['正确', '错误'].map(value => <label className="quiz-option" key={value}><input type="radio" name={check.check_id} checked={answer === value} disabled={busy || check.source_available === false} onChange={() => saveDraft([], value)} />{value}</label>)}
        {check.public_question.form === 'short_answer' && !judgment && <textarea placeholder="写下你的答案或解题思路…" disabled={busy || check.source_available === false} aria-label="检查答案" value={answer} onChange={e => saveDraft(choice, e.target.value)} maxLength={4000} />}
      </> : <div className="quiz-saved-answer" role="status">
        {attempt.status !== 'skipped' && <fieldset aria-label="已保存的作答" disabled>
          <legend>你的作答</legend>
          <ChoiceOptions name={check.check_id} options={check.public_question.options} selected={attempt.option_ids} multiple={!singleChoice} onChange={() => undefined} disabled />
          {check.public_question.form === 'short_answer' && <QuizMarkdown content={attempt.text} />}
        </fieldset>}
        <div className="quiz-feedback">
          {attempt.status === 'graded' ? <strong>{attempt.evaluator === 'model' ? 'AI 参考评价' : '解析'}</strong> : <p>{attempt.status === 'skipped' ? '已跳过，未产生理解证据。' : '答案已保存，评价尚未完成。'}</p>}
          {attempt.feedback && <QuizMarkdown content={attempt.feedback} />}
          {(attempt.status === 'evaluation_failed' || attempt.status === 'pending_evaluation') && <button disabled={busy} onClick={() => void run(() => apiRequest(`/api/self-learning/checks/${check.check_id}/attempts/${attempt.attempt_id}/evaluate`, { method: 'POST' }))}>{busy ? '正在评价…' : '重新评价'}</button>}
        </div>
      </div>}
      <div className="quiz-question-footer">
        {!attempt && <div className="quiz-answer-actions"><button className="quiz-submit" disabled={busy || check.source_available === false || (!choice.length && !answer.trim())} onClick={() => void run(() => submit())}>{busy ? check.public_question.form === 'short_answer' ? '正在批改…' : '正在保存…' : questionNumber ? '提交答案' : '提交检查答案'}</button>
          {!questionNumber && <button className="quiz-skip" disabled={busy} onClick={() => void run(() => submit(true))}>跳过这道检查</button>}
        </div>}
        {onReference && <div className="quiz-help-actions" aria-label="习题辅导操作">
          <button disabled={busy || check.source_available === false} onClick={() => reference('请结合我当前的作答，只给下一步提示，暂时不要给完整答案。')}>提示</button>
          <button disabled={busy || check.source_available === false} onClick={() => reference(attempt && attempt.status !== 'skipped' ? '请结合我这次已提交的答案和评价，完整讲解这道题的解题依据、步骤和易错点。未提供解题过程时，不要推测我的思考过程。' : '请完整讲解这道题的解题依据、步骤和易错点。')}>讲解</button>
        </div>}
      </div>
    </>}
    {!checkId && (!check || attempt) && <button disabled={busy} onClick={() => void run(offer)}>{busy ? '正在准备检查…' : check ? '再来一道检查' : '开始理解检查'}</button>}
    {error && <p role="alert">{error}，仍可继续阅读。</p>}
  </section>;
}
