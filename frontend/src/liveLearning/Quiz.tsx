import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PracticeContext } from './readingContext';
import { CheckCard, type Check } from './CheckCard';
import { QuizMarkdown } from './QuizMarkdown';
import { quizTypeLabel } from './quizPresentation';
import { apiRequest } from '../stitch/api/client';
import { getQuizQuestions } from '../stitch/pages/courseMaterialPreviewData';
import type { CourseMaterial } from '../stitch/api/types';
type Result = { version: number; answers: Record<string, string>; correct: number; graded: number; feedback: { id: string; correct: boolean | null; answer: string; explanation: string }[] };
type QuizNavigation = { onReference?: (index: number, stem: string, practice?: PracticeContext, prompt?: string) => void; onPracticeUpdate?: (index: number, practice: PracticeContext) => void; initialQuestion?: number };
export function QuizLoading({ error, onRetry }: { error?: string; onRetry?: () => void }) {
  return <section className="quiz-loading" aria-label="习题加载" aria-busy={!error}>
    {error ? <div role="alert"><p>习题暂时未能加载，请重试。</p>{onRetry && <button type="button" onClick={onRetry}>重新加载</button>}</div>
      : <div role="status"><span className="quiz-loading-spinner" aria-hidden="true" /><p>正在加载习题…</p></div>}
  </section>;
}

function QuestionFrame({ index, stem, children, onReference, initialQuestion }: QuizNavigation & { index: number; stem: string; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { if (initialQuestion === index) root.current?.scrollIntoView({ block: 'center' }); }, [initialQuestion, index]);
  return <div ref={root} data-quiz-question={index} className={initialQuestion === index ? 'report-reference-fallback' : undefined}>
    {children}{onReference && <button type="button" aria-label={`讲解第 ${index + 1} 题`} onClick={() => onReference(index, stem, undefined, '请完整讲解这道题的解题依据、步骤和易错点。')}>讲解</button>}
  </div>;
}
function LegacyQuiz({ material, ...navigation }: { material: CourseMaterial } & QuizNavigation) {
  const questions = getQuizQuestions(material);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [retry, setRetry] = useState(0);
  const path = `/api/self-learning/courses/${material.course_id}/practice/${material.material_id}`;
  useEffect(() => {
    const controller = new AbortController();
    setReady(false); setError('');
    void apiRequest<Result>(path, { signal: controller.signal }).then(r => {
      if (controller.signal.aborted) return;
      if (r.version === material.version) { setAnswers(r.answers); setResult(r); }
      setReady(true);
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [path, material.version, retry]);
  if (!ready) return <QuizLoading error={error} onRetry={() => setRetry(n => n + 1)} />;
  return <form className="resource-quiz-preview" onSubmit={async e => {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    try { setResult(await apiRequest<Result>(path, { method: 'POST', body: JSON.stringify({ version: material.version || 1, answers }) })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : '提交失败'); } finally { setBusy(false); }
  }}>{questions.map((q, i) => { const id = String(q.id || i); const feedback = result?.feedback.find(f => f.id === id); return <QuestionFrame key={id} index={i} stem={q.stem} {...navigation}><fieldset style={{ marginBottom: 24, padding: 16 }}><legend>第 {i + 1} 题 · {quizTypeLabel(q.type)}</legend><QuizMarkdown content={q.stem} />
    {q.options?.length ? q.options.map((option, n) => <label key={n} className="quiz-option"><input type={q.type === "multiple_choice" ? "checkbox" : "radio"} name={id} value={String.fromCharCode(65 + n)} checked={(answers[id] || '').split(',').includes(String.fromCharCode(65 + n))} onChange={e => { setResult(undefined); const choice = e.target.value; const selected = (answers[id] || '').split(',').filter(Boolean); setAnswers({ ...answers, [id]: q.type === 'multiple_choice' ? (e.target.checked ? [...selected, choice] : selected.filter(a => a !== choice)).sort().join(',') : choice }); }} /><span className="quiz-option-letter" aria-hidden="true">{String.fromCharCode(65 + n)}.</span><QuizMarkdown content={option} /></label>) : q.type === 'true_false' ? ['正确', '错误'].map(value => <label className="quiz-option" key={value}><input type="radio" name={id} checked={answers[id] === value} onChange={() => { setResult(undefined); setAnswers({ ...answers, [id]: value }); }} />{value}</label>) : <textarea aria-label={`第 ${i + 1} 题答案`} value={answers[id] || ''} onChange={e => { setResult(undefined); setAnswers({ ...answers, [id]: e.target.value }); }} />}
    {feedback && <div><p>{feedback.correct === null ? '请对照参考答案自查' : feedback.correct ? '回答正确' : '建议回顾'}</p><QuizMarkdown content={`参考答案：${feedback.answer}\n\n${feedback.explanation}`} /></div>}
  </fieldset></QuestionFrame>; })}{error && <p role="alert">{error}</p>}<button className="quiz-submit" disabled={busy || !questions.length} type="submit">{busy ? '正在保存…' : '提交练习'}</button>{result && <p role="status">已保存 · 自动批改 {result.graded} 题，答对 {result.correct} 题</p>}</form>;
}

export function LiveQuiz({ material, ...navigation }: { material: CourseMaterial } & QuizNavigation) {
  type Snapshot = { key: string; mode: { checks_enabled: boolean; owner: string }; checks?: { topic_id: string; items: Check[] } };
  const key = JSON.stringify([material.course_id, material.material_id, material.version]);
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [failure, setFailure] = useState<{ key: string; message: string }>();
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    setFailure(undefined); setSnapshot(undefined);
    const controller = new AbortController();
    const path = `/api/self-learning/courses/${encodeURIComponent(material.course_id)}/practice/${encodeURIComponent(material.material_id)}`;
    async function load() {
      try {
        const mode = await apiRequest<Snapshot['mode']>(`${path}/mode`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        let checks: Snapshot['checks'];
        if (mode.checks_enabled) {
          checks = await apiRequest<NonNullable<Snapshot['checks']>>(`${path}/checks`, { method: 'POST', body: JSON.stringify({ version: material.version }), signal: controller.signal });
          if (!checks.items.length) throw new Error('没有可用的作答记录');
        }
        // Publish one complete snapshot; never replace a read-only preview with a second question tree.
        if (!controller.signal.aborted) setSnapshot({ key, mode, checks });
      } catch (e) { if (!controller.signal.aborted) setFailure({ key, message: e instanceof Error ? e.message : '练习暂不可用' }); }
    }
    void load(); return () => controller.abort();
  }, [key, material.course_id, material.material_id, material.version, retry]);
  if (!snapshot || snapshot.key !== key) return <QuizLoading error={failure?.key === key ? failure.message : undefined} onRetry={() => setRetry(n => n + 1)} />;
  const { mode, checks } = snapshot;
  if (!mode.checks_enabled) return <LegacyQuiz key={key} material={material} {...navigation} />;
  return <section className="quiz-sheet" aria-label="版本化练习"><header className="quiz-sheet-heading"><h1>{material.title?.replace(/\.(json|md)$/i, '') || '巩固练习'}</h1><span>{checks?.items.length} 道题</span></header>{navigation.initialQuestion !== undefined && checks && navigation.initialQuestion >= checks.items.length && <p role="alert">引用的题目位置不可用，已打开原版本资料。</p>}{checks?.items.map((check, index) => <QuestionFrame key={check.check_id} index={index} stem={check.public_question.stem} initialQuestion={navigation.initialQuestion}><CheckCard questionType={getQuizQuestions(material)[index]?.type} initialCheck={check} checkId={check.check_id} owner={mode.owner} course={material.course_id} topic={checks.topic_id} onReference={navigation.onReference ? (practice, prompt) => navigation.onReference?.(index, check.public_question.stem, practice, prompt) : undefined} onSavedAttempt={practice => navigation.onPracticeUpdate?.(index, practice)} questionNumber={index + 1} /></QuestionFrame>)}</section>;
}
