import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PracticeContext } from './readingContext';
import { CheckCard } from './CheckCard';
import { apiRequest } from '../stitch/api/client';
import { getQuizQuestions } from '../stitch/pages/courseMaterialPreviewData';
import type { CourseMaterial } from '../stitch/api/types';
type Result = { version: number; answers: Record<string, string>; correct: number; graded: number; feedback: { id: string; correct: boolean | null; answer: string; explanation: string }[] };
type QuizNavigation = { onReference?: (index: number, stem: string, practice?: PracticeContext, prompt?: string) => void; onPracticeUpdate?: (index: number, practice: PracticeContext) => void; initialQuestion?: number };
function QuestionFrame({ index, stem, children, onReference, initialQuestion }: QuizNavigation & { index: number; stem: string; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { if (initialQuestion === index) root.current?.scrollIntoView({ block: 'center' }); }, [initialQuestion, index]);
  return <div ref={root} data-quiz-question={index} className={initialQuestion === index ? 'report-reference-fallback' : undefined}>
    {children}{onReference && <button type="button" aria-label={`询问第 ${index + 1} 题`} onClick={() => onReference(index, stem)}>✦ 问这题</button>}
  </div>;
}
function LegacyQuiz({ material, ...navigation }: { material: CourseMaterial } & QuizNavigation) {
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
  }}>{questions.map((q, i) => { const id = String(q.id || i); const feedback = result?.feedback.find(f => f.id === id); return <QuestionFrame key={id} index={i} stem={q.stem} {...navigation}><fieldset style={{ marginBottom: 24, padding: 16 }}><legend>{i + 1}. {q.stem}</legend>
    {q.options?.length ? q.options.map((option, n) => <label key={n} style={{ display: 'block', padding: 8 }}><input type={q.type === "multiple_choice" ? "checkbox" : "radio"} name={id} value={String.fromCharCode(65 + n)} checked={(answers[id] || '').split(',').includes(String.fromCharCode(65 + n))} onChange={e => { setResult(undefined); const choice = e.target.value; const selected = (answers[id] || '').split(',').filter(Boolean); setAnswers({ ...answers, [id]: q.type === 'multiple_choice' ? (e.target.checked ? [...selected, choice] : selected.filter(a => a !== choice)).sort().join(',') : choice }); }} /> {option}</label>) : <textarea aria-label={`第 ${i + 1} 题答案`} value={answers[id] || ''} onChange={e => { setResult(undefined); setAnswers({ ...answers, [id]: e.target.value }); }} />}
    {feedback && <p>{feedback.correct === null ? '请对照参考答案自查' : feedback.correct ? '回答正确' : '建议回顾'} · 参考答案：{feedback.answer}<br />{feedback.explanation}</p>}
  </fieldset></QuestionFrame>; })}{error && <p role="alert">{error}</p>}<button disabled={busy || !questions.length} type="submit">{busy ? '正在保存…' : '提交练习'}</button>{result && <p role="status">已保存 · 自动批改 {result.graded} 题，答对 {result.correct} 题</p>}</form>;
}

export function LiveQuiz({ material, ...navigation }: { material: CourseMaterial } & QuizNavigation) {
  const [mode, setMode] = useState<{ checks_enabled: boolean; owner: string }>();
  const [checks, setChecks] = useState<{ topic_id: string; items: { check_id: string; public_question: { stem: string } }[] }>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    const path = `/api/self-learning/courses/${encodeURIComponent(material.course_id)}/practice/${encodeURIComponent(material.material_id)}`;
    async function load() {
      try {
        const value = await apiRequest<{ checks_enabled: boolean; owner: string }>(`${path}/mode`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setMode(value);
        if (value.checks_enabled) {
          const result = await apiRequest<{ topic_id: string; items: { check_id: string; public_question: { stem: string } }[] }>(`${path}/checks`, { method: 'POST', body: JSON.stringify({ version: material.version }), signal: controller.signal });
          if (!controller.signal.aborted) setChecks(result);
        }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '练习暂不可用'); }
    }
    void load(); return () => controller.abort();
  }, [material.course_id, material.material_id, material.version]);
  if (error) return <p role="alert">{error}，可以继续阅读其他资料。</p>;
  if (!mode) return <p>正在读取练习记录…</p>;
  if (!mode.checks_enabled) return <LegacyQuiz material={material} {...navigation} />;
  return <section aria-label="版本化练习">{navigation.initialQuestion !== undefined && checks && navigation.initialQuestion >= checks.items.length && <p role="alert">引用的题目位置不可用，已打开原版本资料。</p>}{checks?.items.map((check, index) => <QuestionFrame key={check.check_id} index={index} stem={check.public_question.stem} initialQuestion={navigation.initialQuestion}><CheckCard checkId={check.check_id} owner={mode.owner} course={material.course_id} topic={checks.topic_id} onReference={navigation.onReference ? (practice, prompt) => navigation.onReference?.(index, check.public_question.stem, practice, prompt) : undefined} onSavedAttempt={practice => navigation.onPracticeUpdate?.(index, practice)} questionNumber={index + 1} /></QuestionFrame>)}</section>;
}
