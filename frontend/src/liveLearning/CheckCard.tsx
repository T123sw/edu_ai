import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { PracticeContext } from './readingContext';
import { serialPolling } from './serialPolling';

type Attempt = { attempt_id: string; status: string; option_ids: string[]; text: string; correct: boolean | null; feedback: string; evaluator: string | null };
type Teaching = { enabled: boolean; revision: number; feedback?: { status: string; turn_id?: string; error?: string } | null };
type Check = { check_id: string; question_version: number; source_available?: boolean; teaching?: Teaching | null; public_question: { form: 'choice' | 'short_answer'; stem: string; options: { id: string; text: string }[] }; attempts?: Attempt[] };
export function CheckCard({ course, topic, owner, refreshKey, checkId, onReference, onSavedAttempt, questionNumber }: { course: string; topic: string; owner: string; refreshKey?: string; checkId?: string; onReference?: (practice: PracticeContext, prompt?: string) => void; onSavedAttempt?: (practice: PracticeContext) => void; questionNumber?: number }) {
  const [checks, setChecks] = useState<Check[]>([]);
  const [choice, setChoice] = useState<string[]>([]);
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const alive = useRef(true);
  const path = `/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/checks`;
  const authorized = useCallback(() => { try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === owner; } catch { return false; } }, [owner]);
  const refresh = useCallback(async () => {
    if (!authorized()) return;
    const result = checkId ? { items: [await apiRequest<Check>(`/api/self-learning/checks/${encodeURIComponent(checkId)}`)] } : await apiRequest<{ items: Check[] }>(path);
    if (alive.current && authorized()) setChecks(result.items);
  }, [path, authorized, checkId]);
  useEffect(() => { alive.current = true; void refresh().catch(e => setError(e.message)); return () => { alive.current = false; }; }, [refresh, refreshKey]);
  const check = checks[0];
  const attempt = check?.attempts?.[0];
  const feedbackStatus = check?.teaching?.feedback?.status;
  useEffect(() => {
    if (!feedbackStatus || !['pending', 'queued', 'accepted', 'running'].includes(feedbackStatus)) return;
    return serialPolling(async () => { try { await refresh(); } catch { /* keep the saved answer; manual refresh can recover */ } }, 2000);
  }, [feedbackStatus, refresh]);
  const draftKey = check ? `learning-check-draft:${owner}:${check.check_id}` : undefined;
  useEffect(() => {
    if (!draftKey || !authorized()) return;
    setChoice([]); setAnswer(''); setRetrying(false);
    try {
      const saved = JSON.parse(localStorage.getItem(draftKey) || 'null');
      if (saved && Array.isArray(saved.options) && typeof saved.text === 'string') {
        setChoice(saved.options); setAnswer(saved.text); setRetrying(!!saved.retrying);
      }
    } catch { /* a malformed local draft never becomes a submitted answer */ }
  }, [draftKey, authorized]);
  function saveDraft(options: string[], text: string, retry = retrying) {
    setChoice(options); setAnswer(text);
    if (draftKey && authorized()) localStorage.setItem(draftKey, JSON.stringify({ options, text, retrying: retry }));
  }
  function reference(prompt?: string) {
    if (!check || !authorized()) return;
    onReference?.({ check_id: check.check_id, ...(attempt && !retrying ? { attempt_id: attempt.attempt_id } : { draft: { option_ids: choice, text: answer } }) }, prompt);
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
    const saved = await apiRequest<Attempt>(`/api/self-learning/checks/${encodeURIComponent(check.check_id)}/attempts`, { method: 'POST', body: pending.body });
    if (alive.current && authorized()) onSavedAttempt?.({ check_id: check.check_id, attempt_id: saved.attempt_id });
    localStorage.removeItem(key);
    if (draftKey) localStorage.removeItem(draftKey);
    setRetrying(false);
  }
  return <section className="sl-check-card" aria-label="理解检查">
    <strong>检查一下理解</strong><small>可以跳过；单题结果不代表掌握整个知识点。</small>
    {check && <>
      <p>{check.public_question.stem}</p>{check.source_available === false && <p>原资料版本暂不可用，以下保留的是已保存题目和作答；不适用于新版资料。</p>}
      {!attempt || retrying ? <>
        {check.public_question.options.map(option => <label key={option.id}><input type="checkbox" checked={choice.includes(option.id)} onChange={e => saveDraft(e.target.checked ? [...choice, option.id] : choice.filter(id => id !== option.id), answer)} />{option.text}</label>)}
        {check.public_question.form === 'short_answer' && <textarea aria-label="检查答案" value={answer} onChange={e => saveDraft(choice, e.target.value)} maxLength={4000} />}
        <button disabled={busy || check.source_available === false || (!choice.length && !answer.trim())} onClick={() => void run(() => submit())}>提交检查答案</button>
        <button disabled={busy} onClick={() => void run(() => submit(true))}>跳过这道检查</button>
      </> : <div role="status">
        {attempt.status !== 'skipped' && <fieldset aria-label="已保存的作答" disabled>
          <legend>你的作答</legend>
          {check.public_question.options.map(option => <label key={option.id}><input type="checkbox" checked={attempt.option_ids.includes(option.id)} readOnly />{option.text}</label>)}
          {check.public_question.form === 'short_answer' && <p>{attempt.text}</p>}
        </fieldset>}
        <span>{attempt.status === 'skipped' ? '已跳过，未产生理解证据。' : attempt.status === 'graded' ? `${attempt.evaluator === 'model' ? 'AI 评价' : '客观批改'} · ${attempt.correct ? '本题正确' : '建议回顾本题'}` : '答案已保存，评价尚未完成。'}</span>
        <p>{attempt.feedback}</p>
        {attempt.status === 'graded' && <button disabled={busy || check.source_available === false} onClick={() => { setRetrying(true); saveDraft([], '', true); }}>再试一次</button>}
        {(attempt.status === 'evaluation_failed' || attempt.status === 'pending_evaluation') && <button disabled={busy} onClick={() => void run(() => apiRequest(`/api/self-learning/checks/${check.check_id}/attempts/${attempt.attempt_id}/evaluate`, { method: 'POST' }))}>重试评价</button>}
      </div>}
      {onReference && <div aria-label="习题辅导操作">
        <button disabled={busy || check.source_available === false} aria-label={questionNumber ? `询问第 ${questionNumber} 题` : '问这题'} onClick={() => reference()}>✦ 问这题</button>
        <button disabled={busy || check.source_available === false} onClick={() => reference('请结合我当前的作答，只给下一步提示，暂时不要给完整答案。')}>给我提示</button>
        {attempt && !retrying && attempt.status !== 'skipped' && <button disabled={busy || check.source_available === false} onClick={() => reference('请根据我这次已提交的答案和评价讲解，说明答案是否符合题意及原因。未提供解题过程时，不要推测我的思考过程。')}>解释我的答案</button>}
        <button disabled={busy || check.source_available === false} onClick={() => reference('请完整讲解这道题的解题依据、步骤和易错点。')}>完整解析</button>
      </div>}
      {check.teaching && <div aria-label="作答后辅导">
        <label><input type="checkbox" checked={check.teaching.enabled} disabled={busy || check.source_available === false} onChange={e => {
          const enabled = e.target.checked;
          void run(() => apiRequest(`/api/self-learning/checks/${encodeURIComponent(check.check_id)}/teaching`, { method: 'PUT', body: JSON.stringify({ enabled, expected_revision: check.teaching!.revision }) }));
        }} />作答后继续辅导</label>
        <small>开启后，下次提交答案会在当前知识点对话中继续讲解。</small>
        {feedbackStatus && <p role="status">{feedbackStatus === 'succeeded' ? '本次作答的辅导已保存到当前知识点对话。' : feedbackStatus === 'failed' || feedbackStatus === 'canceled' ? '作答已保存，辅导未完成，可在对话中重试或主动提问。' : '作答已保存，正在准备后续辅导…'}</p>}
        {feedbackStatus === 'failed' && check.teaching.feedback?.turn_id && <button disabled={busy} onClick={() => void run(() => apiRequest(`/api/self-learning/agent-turns/${encodeURIComponent(check.teaching!.feedback!.turn_id!)}/retry`, { method: 'POST' }))}>重试本次辅导</button>}
      </div>}
    </>}
    {!checkId && (!check || attempt) && <button disabled={busy} onClick={() => void run(offer)}>{busy ? '正在准备检查…' : check ? '再来一道检查' : '开始理解检查'}</button>}
    {error && <p role="alert">{error}，仍可继续阅读。</p>}
  </section>;
}
