import type { KnowledgeBaseDocument } from "../../api/types";
import { cx } from "../../shared";

const labels: Record<KnowledgeBaseDocument["status"], string> = {
  received: "等待处理",
  parsing: "解析中",
  chunking: "切分中",
  embedding: "向量化中",
  indexing: "索引中",
  ready: "可用于检索",
  partially_ready: "部分可用",
  failed: "处理失败",
};

export function KnowledgeDocumentStatus({ status }: { status: KnowledgeBaseDocument["status"] }) {
  const selectable = status === "ready";
  return <span className={cx("knowledge-document-status", selectable ? "is-ready" : "is-blocked")} data-selectable={selectable}>{labels[status]}</span>;
}
