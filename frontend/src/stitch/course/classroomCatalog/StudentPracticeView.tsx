import { useRef, useState } from "react";
import { submitResourceQuestions } from "../../api/resourceLearning";
import type { ClassroomCatalogResource, QuizAnswers, ResourceLearningProgress } from "../../api/types";
import { getQuizQuestions } from "../../pages/courseMaterialPreviewData";
import { StudentResourceProgressPanel } from "./StudentResourceProgressPanel";
import { isMultipleChoice, practiceOptionValue } from "./practiceAnswers";

type Props = {
  courseId: string;
  resource: ClassroomCatalogResource;
  mode?: "manage" | "learn";
  onProgress?: (progress: ResourceLearningProgress) => void;
  onQuestionFocus?: (questionId: string | null) => void;
};
export function StudentPracticeView({ courseId, resource, mode = "learn", onProgress, onQuestionFocus }: Props) {
  const questions = resource.resource ? getQuizQuestions(resource.resource) : [];
  const required = questions.filter((question) => question.required !== false);
  const [answers, setAnswers] = useState<QuizAnswers>({});
  const [progress, setProgress] = useState(resource.progress ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const attemptKey = useRef<string | null>(null);
  const hasAnswer = (value: string | string[] | undefined) => Array.isArray(value) ? value.length > 0 : Boolean(value?.trim());
  const ready = questions.length > 0 && required.every((question) => hasAnswer(answers[question.id || String(questions.indexOf(question))])) && Object.values(answers).some(hasAnswer);
  const update = (id: string, value: string | string[]) => {
    setAnswers((current) => ({ ...current, [id]: value }));
    setSubmitted(false); setMessage(null); attemptKey.current = null;
  };
  const submit = async () => {
    if (!ready || submitting) return;
    if (mode === "manage") { setSubmitted(true); setMessage("试答已完成，可对照参考答案检查题目质量。"); return; }
    const version = resource.approved_version;
    if (!version) { setMessage("当前习题尚未发布，暂时无法提交。"); return; }
    if (questions.some((question) => !question.id)) { setMessage("题目缺少标识，请联系教师重新生成并发布。"); return; }
    setSubmitting(true); setMessage(null);
    attemptKey.current ??= crypto.randomUUID?.() ?? `practice-${Date.now()}`;
    try {
      const nonEmptyAnswers = Object.fromEntries(Object.entries(answers).filter(([, value]) => hasAnswer(value))) as QuizAnswers;
      const next = await submitResourceQuestions(courseId, resource.material_id, version, attemptKey.current, nonEmptyAnswers);
      setProgress(next); attemptKey.current = null; onProgress?.(next);
      setSubmitted(true);
      setMessage(next.status === "completed" ? `已完成 · 最新答对 ${next.correct_count_latest} 题` : "答案已提交");
    } catch (value) { setMessage(value instanceof Error ? value.message : "答案提交失败"); }
    finally { setSubmitting(false); }
  };
  return <section className="student-practice-view"><header><div><p className="curriculum-node-overview__eyebrow">{mode === "manage" ? "教师试答" : "课程练习"}</p><h2>{resource.resource?.title || "练习题"}</h2></div>{mode === "learn" ? <StudentResourceProgressPanel progress={progress} /> : <span className="catalog-status">试答不计入学生学习记录</span>}</header>
    <div className="student-practice-view__questions">{questions.map((question, index) => {
      const id = question.id || String(index);
      const multiple = isMultipleChoice(question.type);
      return <fieldset disabled={submitting} key={id} onFocus={() => onQuestionFocus?.(question.id || null)}><legend><span>第 {index + 1} 题{multiple ? " · 多选" : ""}</span>{question.stem || "未命名题目"}</legend>
        {question.options?.length ? question.options.map((option, optionIndex) => {
          const value = practiceOptionValue(option, optionIndex);
          const selected = answers[id];
          return <label key={`${value}-${optionIndex}`}><input type={multiple ? "checkbox" : "radio"} name={`${resource.material_id}-${id}`} value={value} checked={multiple ? Array.isArray(selected) && selected.includes(value) : selected === value} onChange={(event) => update(id, multiple ? event.target.checked ? [...(Array.isArray(selected) ? selected : []), value] : (Array.isArray(selected) ? selected : []).filter((item) => item !== value) : value)} /><span>{/^[A-Z][.、:：)）\s]/i.test(option) ? option : `${value}. ${option}`}</span></label>;
        }) : <textarea aria-label={`第 ${index + 1} 题答案`} rows={3} placeholder="在这里填写你的答案…" value={String(answers[id] ?? "")} onChange={(event) => update(id, event.target.value)} />}
        {mode === "manage" && submitted ? <div className="practice-answer"><strong>参考答案：{question.answer || "未提供"}</strong>{question.explanation ? <p>{question.explanation}</p> : null}</div> : null}
      </fieldset>;
    })}</div>
    {!questions.length ? <p className="catalog-panel-message">当前习题暂无可作答的题目。</p> : null}
    <footer><span role="status">{message || `请完成全部 ${required.length} 道必答题`}</span><button type="button" className="catalog-primary-action" disabled={!ready || submitting} onClick={() => void submit()}>{submitting ? "正在提交…" : mode === "manage" ? "提交试答" : "提交答案"}</button></footer>
  </section>;
}
