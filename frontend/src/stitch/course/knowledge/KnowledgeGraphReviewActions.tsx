type Props = {
  busy: boolean;
  dirty: boolean;
  impactAccepted: boolean;
  issueCount: number;
  onImpactAcceptedChange: (accepted: boolean) => void;
  onBack: () => void;
  onSave: () => void;
  onConfirm: () => void;
};

export function KnowledgeGraphReviewActions({
  busy,
  dirty,
  impactAccepted,
  issueCount,
  onImpactAcceptedChange,
  onBack,
  onSave,
  onConfirm,
}: Props) {
  return (
    <footer className="course-kb-graph__actions course-kb-wizard__footer">
      <button type="button" className="course-kb-wizard__secondary" disabled={busy} onClick={onBack}>
        返回教材步骤
      </button>
      <div className="course-kb-graph__actions-main">
        <button type="button" className="course-kb-wizard__secondary" disabled={busy || !dirty} onClick={onSave}>
          保存草案
        </button>
        <label>
          <input
            type="checkbox"
            checked={impactAccepted}
            disabled={busy || issueCount > 0}
            onChange={(event) => onImpactAcceptedChange(event.target.checked)}
          />
          我已审核图谱，确认现有节点均已保留且新增节点内容正确
        </label>
        <button type="button" className="course-kb-wizard__primary" disabled={busy || !impactAccepted || issueCount > 0} onClick={onConfirm}>
          {busy ? "正在处理…" : "确认图谱并开始构建"}
        </button>
      </div>
    </footer>
  );
}
