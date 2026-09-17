import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { getQuizQuestions } from '../stitch/pages/courseMaterialPreviewData';
import type { CourseMaterial } from '../stitch/api/types';
import { CheckCard } from './CheckCard';
type Result = { version: number; answers: Record<string, string>; correct: number; graded: number; feedback: { id: string; correct: boolean | null; answer: string; explanation: string }[] };
export function LiveQuiz({ material }: { material: CourseMaterial }) {
  if ((material as CourseMaterial & { learning_checks_enabled?: boolean }).learning_checks_enabled) return <div>{getQuizQuestions(material).map((q, i) => <CheckCard key={String(q.id || i)} questionId={String(q.id || i)} topicId={material.scope_id || ''} resource={{ course_id: material.course_id, material_type: 'quiz', material_id: material.material_id, version: material.version || 1 }} />)}</div>;
  return <LegacyQuiz material={material} />;
}
function LegacyQuiz({ material }: { material: CourseMaterial }) {
  const questions = getQuizQuestions(material);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const path = `/api/self-learning/courses/${material.course_id}/practice/${material.material_id}`;
  useEffect(() => {
    let active = true;
    void apiRequest<Result>(path).then(r => { if (active && r.version === material.version) { setAnswers(r.answers); setResult(r); } }).catch(e => active && setError(e.message));
    return () => { active = false; };
  }, [path, material.version]);
  return <form className="resource-quiz-preview" onSubmit={async e => {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    try { setResult(await apiRequest<Result>(path, { method: 'POST', body: JSON.stringify({ version: material.version || 1, answers }) })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : '提交失败'); } finally { setBusy(false); }
  }}>{questions.map((q, i) => { const id = String(q.id || i); const feedback = result?.feedback.find(f => f.id === id); return <fieldset key={id} style={{ marginBottom: 24, padding: 16 }}><legend>{i + 1}. {q.stem}</legend>
    {q.options?.length ? q.options.map((option, n) => <label key={n} style={{ display: 'block', padding: 8 }}><input type={q.type === "multiple_choice" ? "checkbox" : "radio"} name={id} value={String.fromCharCode(65 + n)} checked={(answers[id] || '').split(',').includes(String.fromCharCode(65 + n))} onChange={e => { setResult(undefined); const choice = e.target.value; const selected = (answers[id] || '').split(',').filter(Boolean); setAnswers({ ...answers, [id]: q.type === 'multiple_choice' ? (e.target.checked ? [...selected, choice] : selected.filter(a => a !== choice)).sort().join(',') : choice }); }} /> {option}</label>) : <textarea aria-label={`第 ${i + 1} 题答案`} value={answers[id] || ''} onChange={e => { setResult(undefined); setAnswers({ ...answers, [id]: e.target.value }); }} />}
    {feedback && <p>{feedback.correct === null ? '请对照参考答案自查' : feedback.correct ? '回答正确' : '建议回顾'} · 参考答案：{feedback.answer}<br />{feedback.explanation}</p>}
  </fieldset>; })}{error && <p role="alert">{error}</p>}<button disabled={busy || !questions.length} type="submit">{busy ? '正在保存…' : '提交练习'}</button>{result && <p role="status">已保存 · 自动批改 {result.graded} 题，答对 {result.correct} 题</p>}</form>;
}
