import { useState } from "react";
import { reviewStandardResource } from "../../api/standardResources";
import type { ClassroomCatalogResource } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { teacherReviewState } from "./catalogPresentation";

type Props = { courseId: string; resource: ClassroomCatalogResource; onChanged: (materialId: string) => void | Promise<void>; onError?: (message: string) => void };

export function TeacherResourceReviewPanel({ courseId, resource, onChanged, onError }: Props) {
  const state = teacherReviewState(resource);
  const [rejectionReason, setRejectionReason] = useState("");
  const [submitting, setSubmitting] = useState<"approved" | "rejected" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const submit = async (decision: "approved" | "rejected") => {
    const reason = rejectionReason.trim();
    if (decision === "rejected" && !reason) { setMessage("请填写退回原因，便于后续修改。"); return; }
    setSubmitting(decision); setMessage(null);
    try {
      await reviewStandardResource(courseId, resource.material_id, decision, reason);
      setMessage(decision === "approved" ? "已批准并发布" : "已退回修改");
      await onChanged(resource.material_id);
    } catch (value) {
      const detail = value instanceof Error ? value.message : "审核提交失败";
      setMessage(detail); onError?.(detail);
    } finally { setSubmitting(null); }
  };
  return <aside className="teacher-resource-review-panel" aria-label="审核与发布">
    <div><p>审核与发布</p><strong>{state.label}</strong></div>
    {state.canReview ? <><label htmlFor="catalog-rejection-reason">退回原因（退回时必填）</label>
      <textarea id="catalog-rejection-reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} placeholder="说明需要修改的内容" rows={3} />
      <div className="teacher-resource-review-panel__actions">
        <button type="button" disabled={submitting !== null} onClick={() => void submit("rejected")}><MaterialIcon name="undo" />{submitting === "rejected" ? "正在退回…" : "退回修改"}</button>
        <button type="button" className="is-primary" disabled={submitting !== null} onClick={() => void submit("approved")}><MaterialIcon name="publish" />{submitting === "approved" ? "正在发布…" : "批准并发布"}</button>
      </div></> : null}
    {message ? <p className="teacher-resource-review-panel__message" role="status">{message}</p> : null}
  </aside>;
}
