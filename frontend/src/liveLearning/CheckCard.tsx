import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';

type Attempt = { attempt_id: string; status: string; option_ids: string[]; text: string; correct: boolean | null; feedback: string; evaluator: string | null };
type Check = { check_id: string; question_version: number; source_available?: boolean; public_question: { form: 'choice' | 'short_answer'; stem: string; options: { id: string; text: string }[] }; attempts?: Attempt[] };
export function CheckCard({ course, topic, owner, refreshKey, checkId }: { course: string; topic: string; owner: string; refreshKey?: string; checkId?: string }) {
  const [checks, setChecks] = useState<Check[]>([]);
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
  useEffect(() => { alive.current = true; void refresh().catch(e => setError(e.message)); return () => { alive.current = false; }; }, [refresh, refreshKey]);
  const check = checks[0];
  const attempt = check?.attempts?.[0];
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
    await apiRequest(`/api/self-learning/checks/${encodeURIComponent(check.check_id)}/attempts`, { method: 'POST', body: pending.body });
    localStorage.removeItem(key);
  }
  return <section className="sl-check-card" aria-label="理解检查">
    <strong>检查一下理解</strong><small>可以跳过；单题结果不代表掌握整个知识点。</small>
    {check && <>
      <p>{check.public_question.stem}</p>{check.source_available === false && <p>原资料版本暂不可用，以下保留的是已保存题目和作答；不适用于新版资料。</p>}
      {!attempt ? <>
        {check.public_question.options.map(option => <label key={option.id}><input type="checkbox" checked={choice.includes(option.id)} onChange={e => setChoice(s => e.target.checked ? [...s, option.id] : s.filter(id => id !== option.id))} />{option.text}</label>)}
        {check.public_question.form === 'short_answer' && <textarea aria-label="检查答案" value={answer} onChange={e => setAnswer(e.target.value)} maxLength={4000} />}
        <button disabled={busy || check.source_available === false || (!choice.length && !answer.trim())} onClick={() => void run(() => submit())}>提交检查答案</button>
        <button disabled={busy} onClick={() => void run(() => submit(true))}>跳过这道检查</button>
      </> : <div role="status">
        <span>{attempt.status === 'skipped' ? '已跳过，未产生理解证据。' : attempt.status === 'graded' ? `${attempt.evaluator === 'model' ? 'AI 评价' : '客观批改'} · ${attempt.correct ? '本题正确' : '建议回顾本题'}` : '答案已保存，评价尚未完成。'}</span>
        <p>{attempt.feedback}</p>
        {(attempt.status === 'evaluation_failed' || attempt.status === 'pending_evaluation') && <button disabled={busy} onClick={() => void run(() => apiRequest(`/api/self-learning/checks/${check.check_id}/attempts/${attempt.attempt_id}/evaluate`, { method: 'POST' }))}>重试评价</button>}
      </div>}
    </>}
    {!checkId && (!check || attempt) && <button disabled={busy} onClick={() => void run(offer)}>{busy ? '正在准备检查…' : check ? '再来一道检查' : '开始理解检查'}</button>}
    {error && <p role="alert">{error}，仍可继续阅读。</p>}
  </section>;
}
