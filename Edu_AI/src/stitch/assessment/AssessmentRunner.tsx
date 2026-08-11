import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import {
  getStudentAssessment,
  getStudentAssessmentFeedback,
  listStudentAssessmentAttempts,
  revealStudentAssessmentAnswers,
  saveStudentAssessmentAnswers,
  startStudentAssessmentAttempt,
  submitStudentAssessmentAttempt,
} from "../api/learning";
import type { AssessmentAttempt, AssessmentFeedback, StudentAssessment, StudentAssessmentItem } from "../api/types";
import { deriveAssessmentRunnerState } from "./assessmentRunnerState";

type Props = { courseId: string; taskId: string; onVerified: () => void };

function optionId(value: unknown): string {
  return value && typeof value === "object" && "id" in value ? String(value.id) : String(value ?? "");
}

function optionText(value: unknown): string {
  return value && typeof value === "object" && "text" in value ? String(value.text) : String(value ?? "");
}

export function AssessmentRunner({ courseId, taskId, onVerified }: Props) {
  const [assessment, setAssessment] = useState<StudentAssessment | null>(null);
  const [attempts, setAttempts] = useState<AssessmentAttempt[]>([]);
  const [feedback, setFeedback] = useState<AssessmentFeedback | null>(null);
  const [answers, setAnswers] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savedSnapshot = useRef("");
  const activeAttempt = useMemo(() => [...attempts].reverse().find((item) => item.status === "in_progress") ?? null, [attempts]);
  const state = deriveAssessmentRunnerState(attempts, feedback);

  async function load() {
    setError(null);
    try {
      const [nextAssessment, nextAttempts] = await Promise.all([
        getStudentAssessment(courseId, taskId),
        listStudentAssessmentAttempts(courseId, taskId).catch((reason) => {
          if (reason instanceof ApiError && reason.status === 404) return [];
          throw reason;
        }),
      ]);
      setAssessment(nextAssessment);
      setAttempts(nextAttempts);
      setFeedback(nextAttempts.length ? await getStudentAssessmentFeedback(courseId, taskId) : null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "测评加载失败");
    }
  }

  useEffect(() => { void load(); }, [courseId, taskId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!activeAttempt || Object.keys(answers).length === 0) return;
    const snapshot = JSON.stringify(answers);
    if (snapshot === savedSnapshot.current) return;
    const timer = window.setTimeout(() => {
      saveStudentAssessmentAnswers(courseId, taskId, activeAttempt.attempt_id, {
        expected_revision: activeAttempt.draft_revision,
        answers,
      }).then((saved) => {
        savedSnapshot.current = snapshot;
        setAttempts((current) => current.map((item) => item.attempt_id === saved.attempt_id ? saved : item));
      }).catch((reason) => {
        setError(reason instanceof Error ? reason.message : "答案自动保存失败");
      });
    }, 800);
    return () => window.clearTimeout(timer);
  }, [activeAttempt, answers, courseId, taskId]);

  async function begin() {
    setBusy(true); setError(null);
    try {
      const attempt = await startStudentAssessmentAttempt(courseId, taskId);
      setAttempts((current) => current.some((item) => item.attempt_id === attempt.attempt_id)
        ? current.map((item) => item.attempt_id === attempt.attempt_id ? attempt : item)
        : [...current, attempt]);
      setAnswers({});
      savedSnapshot.current = "";
    } catch (reason) { setError(reason instanceof Error ? reason.message : "无法开始测评"); }
    finally { setBusy(false); }
  }

  function updateAnswer(itemId: string, answer: Record<string, unknown>) {
    setAnswers((current) => ({ ...current, [itemId]: answer }));
  }

  async function persistAnswers(): Promise<AssessmentAttempt | null> {
    if (!activeAttempt || Object.keys(answers).length === 0) return activeAttempt;
    const saved = await saveStudentAssessmentAnswers(courseId, taskId, activeAttempt.attempt_id, {
      expected_revision: activeAttempt.draft_revision, answers,
    });
    savedSnapshot.current = JSON.stringify(answers);
    setAttempts((current) => current.map((item) => item.attempt_id === saved.attempt_id ? saved : item));
    return saved;
  }

  async function submit() {
    if (!activeAttempt) return;
    setBusy(true); setError(null);
    try {
      await persistAnswers();
      const submitted = await submitStudentAssessmentAttempt(courseId, taskId, activeAttempt.attempt_id, `assessment-submit:${activeAttempt.attempt_id}`);
      setAttempts((current) => current.map((item) => item.attempt_id === submitted.attempt_id ? submitted : item));
      setFeedback(await getStudentAssessmentFeedback(courseId, taskId));
      if (submitted.result === "passed" || submitted.result === "mastered") onVerified();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "测评提交失败"); }
    finally { setBusy(false); }
  }

  async function reveal() {
    setBusy(true); setError(null);
    try { setFeedback(await revealStudentAssessmentAnswers(courseId, taskId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "答案揭示失败"); }
    finally { setBusy(false); }
  }

  if (!assessment) return <div className="assessment-runner">{error || "正在加载正式测评…"}</div>;
  return (
    <section className="assessment-runner" aria-label="正式测评">
      <header><div><strong>正式测评</strong><span>{assessment.items.length} 题 · 最多 {assessment.max_attempts} 次 · 答案自动保存</span></div>{feedback ? <span>已用 {feedback.attempts_used}/{feedback.max_attempts} 次 · 最佳 {feedback.best_final_score ?? "待评分"}</span> : null}</header>
      {error ? <p className="assessment-runner__error">{error}</p> : null}
      {activeAttempt ? <div className="assessment-runner__questions">
        {assessment.items.map((item) => <Question key={item.assessment_item_id} item={item} value={answers[item.assessment_item_id]} onChange={(value) => updateAnswer(item.assessment_item_id, value)} />)}
        <div className="assessment-runner__actions"><button type="button" className="learning-secondary" disabled={busy} onClick={() => void persistAnswers()}>保存答案</button><button type="button" className="learning-primary" disabled={busy} onClick={() => void submit()}>{busy ? "提交中…" : "提交测评"}</button></div>
      </div> : <AssessmentOutcome state={state} feedback={feedback} />}
      {!activeAttempt && ["ready", "retry"].includes(state) ? <button type="button" className="learning-primary" disabled={busy} onClick={() => void begin()}>{state === "retry" ? "再次测评" : "开始测评"}</button> : null}
      {!activeAttempt && ["passed", "exhausted"].includes(state) ? <button type="button" className="learning-secondary" disabled={busy} onClick={() => void reveal()}>查看答案与解析</button> : null}
      {state === "revealed" && feedback ? <RevealedFeedback feedback={feedback} /> : null}
    </section>
  );
}

function Question({ item, value, onChange }: { item: StudentAssessmentItem; value?: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }) {
  const options = Array.isArray(item.prompt.options) ? item.prompt.options : [];
  return <fieldset className="assessment-runner__question"><legend>{item.position}. {String(item.prompt.stem || "请完成本题")} <small>{item.max_score} 分</small></legend>
    {item.item_type === "single_choice" ? options.map((option) => <label key={optionId(option)}><input type="radio" name={item.assessment_item_id} checked={value?.selected_option_id === optionId(option)} onChange={() => onChange({ selected_option_id: optionId(option) })} />{optionText(option)}</label>)
      : item.item_type === "multiple_choice" ? options.map((option) => { const selected = Array.isArray(value?.selected_option_ids) ? value.selected_option_ids.map(String) : []; const id = optionId(option); return <label key={id}><input type="checkbox" checked={selected.includes(id)} onChange={(event) => onChange({ selected_option_ids: event.target.checked ? [...selected, id] : selected.filter((entry) => entry !== id) })} />{optionText(option)}</label>; })
      : item.item_type === "judge" ? <div><label><input type="radio" name={item.assessment_item_id} checked={value?.value === true} onChange={() => onChange({ value: true })} />正确</label><label><input type="radio" name={item.assessment_item_id} checked={value?.value === false} onChange={() => onChange({ value: false })} />错误</label></div>
      : <textarea className={item.item_type.includes("code") || item.item_type === "debug_fix" ? "is-code" : ""} rows={item.item_type.includes("code") || item.item_type === "debug_fix" ? 8 : 3} value={String(value?.text ?? "")} onChange={(event) => onChange({ text: event.target.value })} placeholder="请输入答案；代码题可直接粘贴代码或运行结果" />}
  </fieldset>;
}

function AssessmentOutcome({ state, feedback }: { state: ReturnType<typeof deriveAssessmentRunnerState>; feedback: AssessmentFeedback | null }) {
  const text = { ready: "完成学习材料后开始正式测评。", in_progress: "测评进行中。", pending_review: "客观题已评分，主观题或代码题正在等待教师复核。", retry: `本次未达及格线，最佳成绩 ${feedback?.best_final_score ?? 0} 分，可继续尝试。`, passed: `已通过正式测评，最佳成绩 ${feedback?.best_final_score ?? 0} 分。`, exhausted: `已用完测评次数，最佳成绩 ${feedback?.best_final_score ?? 0} 分。`, revealed: "答案已揭示，计分尝试已关闭。" }[state];
  return <p className={`assessment-runner__outcome is-${state}`}>{text}</p>;
}

function RevealedFeedback({ feedback }: { feedback: AssessmentFeedback }) {
  return <div className="assessment-runner__feedback">{feedback.items.map((item) => <article key={item.assessment_item_id}><strong>{item.position}. {String(item.prompt.stem || "题目")}</strong><span>得分：{item.final_score ?? "待评分"}/{item.max_score}</span><pre>{JSON.stringify(item.solution ?? item.rubric ?? {}, null, 2)}</pre></article>)}</div>;
}
