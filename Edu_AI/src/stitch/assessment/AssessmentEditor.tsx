import { useEffect, useState } from "react";

import {
  detectTaskAssessment,
  generateTaskAssessment,
  updateTaskAssessmentDraft,
} from "../api/learning";
import type { AssessmentDraft, LearningTask } from "../api/types";
import { getAssessmentPublishBlockers } from "./assessmentAuthoring";

type AssessmentEditorProps = {
  courseId: string;
  task: LearningTask;
  onDraftChange: (taskId: string, draft: AssessmentDraft | null) => void;
};

export function AssessmentEditor({ courseId, task, onDraftChange }: AssessmentEditorProps) {
  const [draft, setDraft] = useState<AssessmentDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDraft(null);
    onDraftChange(task.task_id, null);
    setError(null);
    setNotice(null);
    detectTaskAssessment(courseId, task.task_id)
      .then((value) => {
        if (cancelled) return;
        setDraft(value);
        onDraftChange(task.task_id, value);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "测评读取失败");
      });
    return () => { cancelled = true; };
  }, [courseId, onDraftChange, task.task_id]);

  async function saveDraft() {
    if (!draft || draft.status !== "draft") return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateTaskAssessmentDraft(courseId, task.task_id, {
        expected_revision: draft.draft_revision,
        pass_threshold: draft.pass_threshold,
        mastery_threshold: draft.mastery_threshold,
        max_attempts: draft.max_attempts,
        assessment_mode: draft.assessment_mode,
        answer_reveal_policy: draft.answer_reveal_policy,
        shuffle_questions: draft.shuffle_questions,
        shuffle_options: draft.shuffle_options,
        items: draft.items,
      });
      setDraft(updated);
      onDraftChange(task.task_id, updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "测评保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function generateDraft() {
    if (!draft || draft.status !== "draft") return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await generateTaskAssessment(
        courseId,
        task.task_id,
        draft.draft_revision,
      );
      setDraft(updated);
      onDraftChange(task.task_id, updated);
      if (updated.items.length === 0) {
        setError("没有生成题目。请确认材料包含可解析正文，并检查模型配置后重试。");
      } else {
        setNotice(`已生成 ${updated.items.length} 道测评题，请检查题目后保存设置。`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "测评生成失败");
    } finally {
      setBusy(false);
    }
  }

  const update = <K extends keyof AssessmentDraft>(key: K, value: AssessmentDraft[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  };
  const blockers = getAssessmentPublishBlockers(draft);

  return (
    <section className="assessment-editor" aria-label="正式测评配置">
      <ol className="assessment-editor__steps">
        <li className="is-complete"><strong>1</strong><span>任务目标</span></li>
        <li className="is-complete"><strong>2</strong><span>学习材料</span></li>
        <li className={draft?.quality.publishable ? "is-complete" : "is-active"}><strong>3</strong><span>正式测评</span></li>
        <li className="is-active"><strong>4</strong><span>发布设置</span></li>
      </ol>
      {error ? <p className="assessment-editor__error">{error}</p> : null}
      {notice ? <p className="assessment-editor__notice">{notice}</p> : null}
      {!draft ? <p className="assessment-editor__loading">正在识别学习材料中的习题…</p> : (
        <>
          <header className="assessment-editor__head">
            <div><h4>正式测评</h4><p>{draft.source_mode === "imported" ? `已从学习材料导入 ${draft.items.length} 道题` : "材料中未识别到可直接使用的习题"}</p></div>
            <span className={draft.quality.publishable ? "is-ready" : "is-blocked"}>{draft.quality.publishable ? "可发布" : "需要完善"}</span>
          </header>
          <div className="assessment-editor__items">
            {draft.items.map((item, index) => (
              <article key={item.assessment_item_id}>
                <span>第 {index + 1} 题 · {item.item_type}</span>
                <strong>{String(item.prompt.stem || "未填写题干")}</strong>
                <small>{item.created_origin === "imported" ? "来自已有习题" : "教师创建"} · {item.max_score} 分</small>
              </article>
            ))}
          </div>
          {draft.items.length === 0 && draft.status === "draft" ? (
            <button type="button" className="learning-secondary" disabled={busy} onClick={() => void generateDraft()}>
              {busy ? "正在分析材料并生成测评…" : "根据学习材料生成测评草稿"}
            </button>
          ) : null}
          <div className="assessment-editor__settings">
            <label>及格线<input type="number" min="0" max="100" value={draft.pass_threshold} disabled={draft.status !== "draft"} onChange={(event) => update("pass_threshold", Number(event.target.value))} /></label>
            <label>掌握线<input type="number" min="0" max="100" value={draft.mastery_threshold} disabled={draft.status !== "draft"} onChange={(event) => update("mastery_threshold", Number(event.target.value))} /></label>
            <label>最多提交次数<input type="number" min="1" max="10" value={draft.max_attempts} disabled={draft.status !== "draft"} onChange={(event) => update("max_attempts", Number(event.target.value))} /></label>
            <label>测评方式<select value={draft.assessment_mode} disabled={draft.status !== "draft"} onChange={(event) => update("assessment_mode", event.target.value as AssessmentDraft["assessment_mode"])}><option value="closed_book">闭卷</option><option value="open_book">开卷</option></select></label>
            <label className="assessment-editor__check"><input type="checkbox" checked={draft.shuffle_questions} disabled={draft.status !== "draft"} onChange={(event) => update("shuffle_questions", event.target.checked)} />随机题序</label>
            <label className="assessment-editor__check"><input type="checkbox" checked={draft.shuffle_options} disabled={draft.status !== "draft"} onChange={(event) => update("shuffle_options", event.target.checked)} />随机选项</label>
          </div>
          {blockers.length ? <ul className="assessment-editor__issues">{blockers.map((item) => <li key={item}>{item}</li>)}</ul> : null}
          {draft.status === "draft" ? <button type="button" className="learning-secondary" disabled={busy} onClick={() => void saveDraft()}>{busy ? "保存中…" : "保存测评设置"}</button> : <p className="assessment-editor__frozen">该测评版本已随任务发布并冻结。</p>}
        </>
      )}
    </section>
  );
}
