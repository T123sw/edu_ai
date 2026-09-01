import { useEffect, useState } from "react";

import { getTaskAssessmentAnalytics, reviewAssessmentAttempt } from "../api/learning";
import type { AssessmentAnalytics as AssessmentAnalyticsData, AssessmentAnalyticsStudent } from "../api/types";
import { formatAssessmentRatio, getAssessmentQueueLabel } from "./assessmentAnalyticsPresentation";

type Props = { courseId: string; taskId: string; onReviewed: () => void };

export function AssessmentAnalytics({ courseId, taskId, onReviewed }: Props) {
  const [report, setReport] = useState<AssessmentAnalyticsData | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [studentComment, setStudentComment] = useState("");
  const [privateComment, setPrivateComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setReport(await getTaskAssessmentAnalytics(courseId, taskId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "测评分析加载失败"); }
  }
  useEffect(() => { void load(); }, [courseId, taskId]); // eslint-disable-line react-hooks/exhaustive-deps

  function openReview(student: AssessmentAnalyticsStudent) {
    setReviewing(student.student_id);
    setScores(Object.fromEntries(student.review_items.map((item) => [item.assessment_item_id, Number(item.ai_suggestion?.suggested_score ?? 0)])));
    setStudentComment(""); setPrivateComment(""); setError(null);
  }

  async function submitReview(student: AssessmentAnalyticsStudent) {
    if (!student.review_attempt_id) return;
    setBusy(true); setError(null);
    try {
      await reviewAssessmentAttempt(courseId, taskId, student.review_attempt_id, {
        item_scores: scores,
        reason_code: "RUBRIC_CONFIRMED",
        student_comment: studentComment,
        private_comment: privateComment,
      });
      setReviewing(null);
      await load();
      onReviewed();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "复核提交失败"); }
    finally { setBusy(false); }
  }

  if (!report) return <section className="assessment-analytics">{error || "正在汇总正式测评…"}</section>;
  return <section className="assessment-analytics" aria-label="正式测评分析">
    <header><div><h4>正式测评反馈</h4><p>所有比例均显示样本分母；待复核不计入最终平均分。</p></div></header>
    {error ? <p className="assessment-runner__error">{error}</p> : null}
    <div className="assessment-analytics__metrics">
      <Metric label="参与率" value={formatAssessmentRatio(report.participation)} />
      <Metric label="提交率" value={formatAssessmentRatio(report.submission)} />
      <Metric label="通过率" value={formatAssessmentRatio(report.pass)} />
      <Metric label="掌握率" value={formatAssessmentRatio(report.mastery)} />
      <Metric label="待复核" value={report.pending_review} />
      <Metric label="平均最佳分" value={report.mean_best_score ?? "—"} />
      <Metric label="中位最佳分" value={report.median_best_score ?? "—"} />
      <Metric label="平均作答次数" value={report.average_attempts} />
    </div>
    <div className="assessment-analytics__table">
      <div className="is-head"><span>学生</span><span>队列</span><span>最佳分</span><span>次数</span><span>操作</span></div>
      {report.students.map((student) => <div className="assessment-analytics__student" key={student.student_id}>
        <div><strong>{student.student_id}</strong><span>{getAssessmentQueueLabel(student.status)}</span><span>{student.best_final_score ?? "—"}</span><span>{student.attempts_used}/{student.max_attempts || "—"}</span><span>{student.status === "pending_review" ? <button type="button" className="learning-secondary" onClick={() => openReview(student)}>复核</button> : "—"}</span></div>
        {reviewing === student.student_id ? <div className="assessment-review-form">
          {student.review_items.map((item) => <article key={item.assessment_item_id}><strong>{String(item.prompt.stem || "主观题/代码题")}</strong><pre>{JSON.stringify(item.answer, null, 2)}</pre><small>量规：{JSON.stringify(item.rubric)}</small><label>最终得分（0–{item.max_score}）<input type="number" min="0" max={item.max_score} value={scores[item.assessment_item_id] ?? 0} onChange={(event) => setScores((current) => ({ ...current, [item.assessment_item_id]: Number(event.target.value) }))} /></label></article>)}
          <label>学生可见评语<textarea rows={2} value={studentComment} onChange={(event) => setStudentComment(event.target.value)} /></label>
          <label>教师私有备注<textarea rows={2} value={privateComment} onChange={(event) => setPrivateComment(event.target.value)} /></label>
          <button type="button" className="learning-primary" disabled={busy} onClick={() => void submitReview(student)}>{busy ? "提交中…" : "提交复核"}</button>
        </div> : null}
      </div>)}
    </div>
    <div className="assessment-analytics__breakdown"><section><h5>题目分析</h5>{report.items.map((item) => <p key={item.assessment_item_id}>{item.position}. {String(item.prompt.stem || "题目")}<span>满分率 {formatAssessmentRatio(item.full_score_rate)}</span></p>)}</section><section><h5>知识点分析</h5>{report.knowledge_points.map((point) => <p key={point.knowledge_point_id}>{point.knowledge_point_id}<span>满分率 {formatAssessmentRatio(point.full_score_rate)}</span></p>)}</section></div>
  </section>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}
