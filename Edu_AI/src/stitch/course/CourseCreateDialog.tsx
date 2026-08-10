import { useEffect, useState, type FormEvent } from "react";

import { createCourse } from "../api/courses";
import type { BackendCourse } from "../api/types";
import { MaterialIcon } from "../shared";
import {
  buildCourseCreatePayload,
  COURSE_DIFFICULTY_OPTIONS,
  COURSE_LANGUAGE_OPTIONS,
  EMPTY_COURSE_CREATION_DRAFT,
  type CourseCreationDraft,
  type CourseCreationErrors,
} from "./courseCreation";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (course: BackendCourse) => void;
};

export function CourseCreateDialog({ open, onClose, onCreated }: Props) {
  const [draft, setDraft] = useState<CourseCreationDraft>(EMPTY_COURSE_CREATION_DRAFT);
  const [errors, setErrors] = useState<CourseCreationErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open, submitting]);

  if (!open) return null;

  function update<K extends keyof CourseCreationDraft>(key: K, value: CourseCreationDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = buildCourseCreatePayload(draft);
    setErrors(result.errors);
    setSubmitError(null);
    if (!result.payload) return;

    setSubmitting(true);
    try {
      const course = await createCourse(result.payload);
      setDraft(EMPTY_COURSE_CREATION_DRAFT);
      onCreated(course);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "课程创建失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="course-create" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget && !submitting) onClose();
    }}>
      <section className="course-create__dialog" role="dialog" aria-modal="true" aria-labelledby="course-create-title">
        <header className="course-create__head">
          <div>
            <p>新课程</p>
            <h2 id="course-create-title">创建课程并准备知识库</h2>
            <span>这些信息会用于规划知识结构、发现和审查课程来源。</span>
          </div>
          <button type="button" onClick={onClose} disabled={submitting} aria-label="关闭创建课程窗口">
            <MaterialIcon name="close" />
          </button>
        </header>

        <form onSubmit={submit} noValidate>
          <label>
            <span>课程名称</span>
            <input autoFocus value={draft.title} onChange={(event) => update("title", event.target.value)} aria-invalid={Boolean(errors.title)} />
            {errors.title ? <small role="alert">{errors.title}</small> : null}
          </label>
          <label>
            <span>课程简介</span>
            <textarea rows={3} value={draft.description} onChange={(event) => update("description", event.target.value)} placeholder="说明课程主题、范围和教学侧重点" aria-invalid={Boolean(errors.description)} />
            {errors.description ? <small role="alert">{errors.description}</small> : null}
          </label>
          <label>
            <span>教学对象 / 年级</span>
            <input value={draft.audience} onChange={(event) => update("audience", event.target.value)} placeholder="例如：高一学生、计算机专业大一学生" aria-invalid={Boolean(errors.audience)} />
            {errors.audience ? <small role="alert">{errors.audience}</small> : null}
          </label>
          <label>
            <span>课程目标</span>
            <textarea rows={4} value={draft.objectivesText} onChange={(event) => update("objectivesText", event.target.value)} placeholder={"每行一个目标，例如：\n理解线性代数的核心概念\n能用矩阵解决实际问题"} aria-invalid={Boolean(errors.objectivesText)} />
            {errors.objectivesText ? <small role="alert">{errors.objectivesText}</small> : null}
          </label>
          <div className="course-create__row">
            <label>
              <span>授课语言</span>
              <select value={draft.language} onChange={(event) => update("language", event.target.value)}>
                {COURSE_LANGUAGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>课程难度</span>
              <select value={draft.difficulty} onChange={(event) => update("difficulty", event.target.value)}>
                {COURSE_DIFFICULTY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>

          {submitError ? <div className="course-create__error" role="alert">{submitError}</div> : null}
          <footer className="course-create__actions">
            <button type="button" className="is-secondary" onClick={onClose} disabled={submitting}>取消</button>
            <button type="submit" className="is-primary" disabled={submitting}>
              {submitting ? "正在创建…" : "创建并继续"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
