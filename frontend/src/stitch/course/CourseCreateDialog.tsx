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
  onCreated: (course: BackendCourse, knowledgeRequirements: string) => void;
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
      onCreated(course, result.knowledgeRequirements);
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
            <input autoFocus value={draft.title} onChange={(event) => update("title", event.target.value)} placeholder="例如：高中 Python 编程基础" aria-invalid={Boolean(errors.title)} />
            {errors.title ? <small role="alert">{errors.title}</small> : null}
          </label>
          <label>
            <span>课程简介</span>
            <textarea rows={3} value={draft.description} onChange={(event) => update("description", event.target.value)} placeholder="例如：通过 16 课时的讲解和上机练习，帮助零基础学生掌握 Python 基础语法与问题求解。" aria-invalid={Boolean(errors.description)} />
            {errors.description ? <small role="alert">{errors.description}</small> : null}
          </label>
          <label>
            <span>教学对象 / 年级</span>
            <input value={draft.audience} onChange={(event) => update("audience", event.target.value)} placeholder="例如：没有编程基础的高一学生" aria-invalid={Boolean(errors.audience)} />
            {errors.audience ? <small role="alert">{errors.audience}</small> : null}
          </label>
          <label>
            <span>课程目标</span>
            <textarea rows={4} value={draft.objectivesText} onChange={(event) => update("objectivesText", event.target.value)} placeholder={"每行一个目标，例如：\n能使用变量、条件和循环编写简单程序\n能定位并修正常见语法错误\n能独立完成一个小型数据处理项目"} aria-invalid={Boolean(errors.objectivesText)} />
            {errors.objectivesText ? <small role="alert">{errors.objectivesText}</small> : null}
          </label>
          <label>
            <span>知识库构建要求</span>
            <textarea
              rows={5}
              value={draft.knowledgeRequirements}
              onChange={(event) => update("knowledgeRequirements", event.target.value)}
              placeholder={"例如：用 8 课时覆盖进程、调度、同步、死锁和虚拟内存，达到本科基础到应用深度；优先使用 MIT、Stanford 等大学课程和公认教材，资料不足时允许 AI 基于来源补充；每个主题包含机制讲解、1 个可验证案例和 3 道带答案解析的练习。"}
              aria-invalid={Boolean(errors.knowledgeRequirements)}
            />
            {errors.knowledgeRequirements ? <small role="alert">{errors.knowledgeRequirements}</small> : null}
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
