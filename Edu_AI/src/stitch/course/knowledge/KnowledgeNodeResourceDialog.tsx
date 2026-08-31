import { useEffect } from "react";

import type { StandardResourceSlot } from "../../api/types";
import { MaterialIcon } from "../../shared";
import {
  canApproveStandardResource,
  STANDARD_RESOURCE_KIND_META,
  standardResourceBody,
  standardReviewLabel,
} from "./standardLearningResourcesPresentation";

export function KnowledgeNodeResourceDialog({
  leafTitle,
  slot,
  canManage,
  busy,
  onApprove,
  onClose,
}: {
  leafTitle: string;
  slot: StandardResourceSlot;
  canManage: boolean;
  busy: boolean;
  onApprove: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const meta = STANDARD_RESOURCE_KIND_META[slot.standard_kind];
  const title = String(slot.resource?.title || `${leafTitle}${meta.label}`);

  return (
    <div
      className="knowledge-resource-dialog__backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        className="knowledge-resource-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="knowledge-resource-dialog-title"
      >
        <header>
          <div>
            <span>{leafTitle} · {meta.label}</span>
            <h2 id="knowledge-resource-dialog-title">{title}</h2>
          </div>
          <button type="button" aria-label="关闭资源详情" onClick={onClose}>
            <MaterialIcon name="close" />
          </button>
        </header>
        <div className="knowledge-resource-dialog__body">
          <pre>{standardResourceBody(slot)}</pre>
        </div>
        <footer>
          <span className={`knowledge-node-resource__status knowledge-node-resource__status--${slot.review_status}`}>
            {standardReviewLabel(slot.review_status)}
          </span>
          <div>
            <button type="button" onClick={onClose}>关闭</button>
            {canApproveStandardResource(canManage, slot) ? (
              <button
                type="button"
                className="is-primary"
                disabled={busy}
                onClick={onApprove}
              >
                <MaterialIcon name="check_circle" />
                {busy ? "正在通过…" : "通过审核"}
              </button>
            ) : null}
          </div>
        </footer>
      </section>
    </div>
  );
}
