import type { ClassroomCatalogProgress } from "../../api/types";

export function StudentResourceProgressPanel({ progress }: { progress?: ClassroomCatalogProgress | null }) {
  if (!progress) return <div className="student-resource-progress is-empty"><strong>尚未开始</strong><span>开始学习后，这里会显示进度。</span></div>;
  const label = progress.status === "completed" ? "已完成" : progress.status === "in_progress" ? "学习中" : "未开始";
  return <div className={`student-resource-progress is-${progress.status}`} aria-live="polite">
    <strong>{label}</strong>
    {progress.completion_basis === "classroom_requirements" ? <span>讲解覆盖 {Math.round(progress.explanation_coverage_percent)}% · 问题 {progress.answered_question_count}/{progress.required_question_count}</span> : null}
    {progress.completion_basis === "required_questions_submitted" ? <span>已作答 {progress.answered_question_count}/{progress.required_question_count}</span> : null}
    {progress.completion_basis === "explicit_read" ? <span>{progress.status === "completed" ? "已确认完成阅读" : "已打开学习资料"}</span> : null}
  </div>;
}
