import { useRef, useState } from "react";
import { submitResourceQuestions } from "../../api/resourceLearning";
import type { ClassroomCatalogResource, QuizAnswers, ResourceLearningProgress } from "../../api/types";
import { getQuizQuestions } from "../../pages/courseMaterialPreviewData";
import { StudentResourceProgressPanel } from "./StudentResourceProgressPanel";

type Props = { courseId: string; resource: ClassroomCatalogResource; onProgress?: (progress: ResourceLearningProgress) => void };
export function StudentPracticeView({ courseId, resource, onProgress }: Props) {
  const questions = resource.resource ? getQuizQuestions(resource.resource) : [];
  const required = questions.filter((question) => question.required !== false && question.id);
  const [answers, setAnswers] = useState<QuizAnswers>({});
  const [progress, setProgress] = useState(resource.progress ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const attemptKey = useRef<string | null>(null);
  const ready = required.length > 0 && required.every((question) => String(answers[question.id!] ?? "").trim());
  const submit = async () => {
    const version = resource.approved_version ?? resource.current_version;
    if (!version || !ready) return;
    setSubmitting(true); setMessage(null);
    attemptKey.current ??= crypto.randomUUID?.() ?? `practice-${Date.now()}`;
    try {
      const nonEmptyAnswers = Object.fromEntries(Object.entries(answers).filter(([, value]) => Array.isArray(value) ? value.length : value.trim())) as QuizAnswers;
      const next = await submitResourceQuestions(courseId, resource.material_id, version, attemptKey.current, nonEmptyAnswers);
      setProgress(next); attemptKey.current = null; onProgress?.(next);
      setMessage(next.status === "completed" ? `已完成 · 最新答对 ${next.correct_count_latest} 题` : "答案已提交");
    } catch (value) { setMessage(value instanceof Error ? value.message : "答案提交失败"); }
    finally { setSubmitting(false); }
  };
  return <section className="student-practice-view"><header><div><p className="curriculum-node-overview__eyebrow">课程练习</p><h2>{resource.resource?.title || "练习题"}</h2></div><StudentResourceProgressPanel progress={progress} /></header>
    <div className="student-practice-view__questions">{questions.map((question, index) => <fieldset key={question.id || index}><legend><span>第 {index + 1} 题</span>{question.stem || "未命名题目"}</legend>
      {question.options?.length ? question.options.map((option) => <label key={option}><input type="radio" name={question.id || String(index)} value={option} checked={answers[question.id || String(index)] === option} onChange={() => setAnswers((current) => ({ ...current, [question.id || String(index)]: option }))} />{option}</label>)
        : <input aria-label={`第 ${index + 1} 题答案`} value={String(answers[question.id || String(index)] ?? "")} onChange={(event) => setAnswers((current) => ({ ...current, [question.id || String(index)]: event.target.value }))} />}
    </fieldset>)}</div>
    <footer><span role="status">{message || `请完成全部 ${required.length} 道必答题`}</span><button type="button" className="catalog-primary-action" disabled={!ready || submitting} onClick={() => void submit()}>{submitting ? "正在提交…" : "提交答案"}</button></footer>
  </section>;
}
