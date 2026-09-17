import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { ResourceRef } from './readingContext';
type Check = { allow_submission?: boolean; check_id: string; item_type: string; prompt: { stem: string; options?: { id: string; text: string }[] } };
type Attempt = { request_id: string; status: string; correct: boolean | null; feedback: string; answer: Record<string, unknown> };
export function CheckCard({ resource, topicId, questionId, checkId }: { resource?: ResourceRef; topicId: string; questionId?: string; checkId?: string }) {
  const [check, setCheck] = useState<Check>();
  const [attempt, setAttempt] = useState<Attempt>();
  const [answer, setAnswer] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<{ fingerprint: string; id: string }>();
  const key = JSON.stringify(resource);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const value = checkId ? await apiRequest<Check>(`/api/self-learning/checks/${encodeURIComponent(checkId)}`) : await apiRequest<Check>(`/api/self-learning/courses/${encodeURIComponent(resource!.course_id)}/topics/${encodeURIComponent(topicId)}/checks`, { method: 'POST', body: JSON.stringify({ resource_ref: resource, question_id: questionId }) });
        const saved = await apiRequest<{ attempts: Attempt[] }>(`/api/self-learning/checks/${value.check_id}/attempts`);
        if (active) {
          setCheck(value); const previous = saved.attempts.at(-1);
          const pending = JSON.parse(localStorage.getItem(`learning-check-pending:${value.check_id}`) || 'null');
          request.current = pending || undefined;
          setAttempt(previous);
          setAnswer(pending ? JSON.parse(pending.fingerprint).answer : previous?.answer || {});
        }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : '检查读取失败'); }
    })();
    return () => { active = false; };
  // Resource identity is serialized so parent rerenders do not re-offer checks.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, topicId, questionId, checkId]);
  const submit = async (skip = false) => {
    if (!check || busy || check.allow_submission === false) return;
    const body = { answer: skip ? {} : answer, skip }; const fingerprint = JSON.stringify(body);
    if (request.current?.fingerprint !== fingerprint) request.current = { fingerprint, id: crypto.randomUUID() };
    setBusy(true); setError('');
    try {
      localStorage.setItem(`learning-check-pending:${check.check_id}`, JSON.stringify(request.current));
      setAttempt(await apiRequest<Attempt>(`/api/self-learning/checks/${check.check_id}/attempts`, { method: 'POST', body: JSON.stringify({ ...body, request_id: request.current.id }) }));
      localStorage.removeItem(`learning-check-pending:${check.check_id}`);
    }
    catch (e) { setError(e instanceof Error ? e.message : '提交失败，答案仍保留'); } finally { setBusy(false); }
  };
  return <fieldset disabled={busy || check?.allow_submission === false} style={{ marginBottom: 20, padding: 16 }}><legend>{check?.prompt.stem || '正在读取检查题…'}</legend>
    {check?.prompt.options?.map(option => <label key={option.id} style={{ display: 'block' }}><input type={check.item_type === 'multiple_choice' ? 'checkbox' : 'radio'} name={check.check_id} checked={check.item_type === 'multiple_choice' ? ((answer.selected_option_ids || []) as string[]).includes(option.id) : answer.selected_option_id === option.id} onChange={e => {
      setAttempt(undefined); const ids = (answer.selected_option_ids || []) as string[];
      setAnswer(check.item_type === 'multiple_choice' ? { selected_option_ids: e.target.checked ? [...ids, option.id] : ids.filter(id => id !== option.id) } : { selected_option_id: option.id });
    }} />{option.text}</label>)}
    {check?.item_type === 'judge' ? <select aria-label="判断答案" value={String(answer.value ?? '')} onChange={e => setAnswer({ value: e.target.value === 'true' })}><option value="" disabled>请选择</option><option value="true">正确</option><option value="false">错误</option></select> : check && !check.prompt.options?.length && <textarea aria-label="检查题答案" value={String(answer.text || '')} onChange={e => setAnswer({ text: e.target.value })} />}
    {check && <div><button type="button" onClick={() => void submit()}>保存作答</button><button type="button" onClick={() => void submit(true)}>跳过</button></div>}
    {check && attempt && ['pending_review', 'evaluating'].includes(attempt.status) && <button type="button" onClick={async () => {
      setBusy(true); setError('');
      try { setAttempt(await apiRequest<Attempt>(`/api/self-learning/checks/${check.check_id}/attempts/${attempt.request_id}/evaluate`, { method: 'POST' })); }
      catch (e) { setError(e instanceof Error ? e.message : '评价失败，已保存答案可重试'); }
      finally { setBusy(false); }
    }}>评价已保存答案</button>}
    {check?.allow_submission === false && <p>这是旧版本检查，保留历史作答；新作答请打开当前版本。</p>}{error && <p role="alert">{error}</p>}{attempt && <p role="status">{attempt.status === 'skipped' ? '已跳过' : attempt.correct === true ? '本题证据支持回答正确' : attempt.correct === false ? '本题建议回顾' : '答案已保存，尚未完成评价'} · {attempt.feedback}</p>}
  </fieldset>;
}
