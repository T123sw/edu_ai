import { useEffect, useMemo, useState } from "react";

import { getStandardResources } from "../../api/standardResources";
import type { StandardResourceLeaf, StandardResourceSlot } from "../../api/types";
import { MaterialIcon } from "../../shared";
import {
  STANDARD_RESOURCE_KIND_META,
  standardResourceLeavesForKnowledgeScope,
  standardReviewLabel,
} from "./standardLearningResourcesPresentation";

function previewText(slot: StandardResourceSlot): string {
  const resource = (slot.resource || {}) as Record<string, unknown>;
  for (const key of ["final_markdown", "markdown", "report_content", "text", "content"]) {
    const value = resource[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "该课程资料已经生成，可在资源中心查看完整内容。";
}

export function KnowledgeNodeCourseResources({
  courseId,
  nodeLabel,
  scopeNodeIds,
}: {
  courseId: string;
  nodeLabel: string;
  scopeNodeIds: ReadonlySet<string>;
}) {
  const [leaves, setLeaves] = useState<StandardResourceLeaf[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedMaterialId, setExpandedMaterialId] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    const load = () => {
      setLoading(true);
      getStandardResources(courseId)
        .then((catalog) => {
          if (!cancelled) {
            setLeaves(catalog.leaves);
            setError("");
          }
        })
        .catch((reason) => {
          if (!cancelled) {
            setError(reason instanceof Error ? reason.message : "课程资料暂时无法读取");
          }
        })
        .finally(() => !cancelled && setLoading(false));
    };
    const handleMaterialUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ courseId?: string }>).detail;
      if (!detail?.courseId || detail.courseId === courseId) load();
    };
    load();
    window.addEventListener("edu-ai:course-material-updated", handleMaterialUpdated);
    return () => {
      cancelled = true;
      window.removeEventListener("edu-ai:course-material-updated", handleMaterialUpdated);
    };
  }, [courseId]);

  const scopedLeaves = useMemo(
    () => standardResourceLeavesForKnowledgeScope(leaves, scopeNodeIds),
    [leaves, scopeNodeIds],
  );
  const resources = scopedLeaves.flatMap((leaf) => leaf.slots
    .filter((slot) => Boolean(slot.resource))
    .map((slot) => ({ leaf, slot })));

  return (
    <section className="knowledge-node-resources" aria-label="课程资料">
      <header className="knowledge-node-resources__header">
        <div>
          <span>课程资料</span>
          <h2>{nodeLabel}</h2>
          <p>展示当前知识节点及其子节点已经生成的课堂、学习指南和练习。</p>
        </div>
        <strong>{resources.length} 项</strong>
      </header>
      {error ? <p className="knowledge-node-resources__state knowledge-node-resources__state--error">{error}</p> : null}
      {!error && loading ? <p className="knowledge-node-resources__state">正在读取课程资料…</p> : null}
      {!error && !loading && resources.length === 0 ? (
        <p className="knowledge-node-resources__state">当前节点暂无已生成课程资料</p>
      ) : null}
      {resources.length > 0 ? (
        <div className="knowledge-node-resources__list">
          {resources.map(({ leaf, slot }) => {
            const meta = STANDARD_RESOURCE_KIND_META[slot.standard_kind];
            const expanded = expandedMaterialId === slot.material_id;
            return (
              <article key={`${leaf.leaf_id}:${slot.material_id}`} className="knowledge-node-resource">
                <button
                  type="button"
                  className="knowledge-node-resource__summary"
                  aria-expanded={expanded}
                  onClick={() => setExpandedMaterialId((current) => current === slot.material_id ? null : slot.material_id)}
                >
                  <span className="knowledge-node-resource__icon"><MaterialIcon name={meta.icon} /></span>
                  <span className="knowledge-node-resource__copy">
                    <strong>{String(slot.resource?.title || `${leaf.title}${meta.label}`)}</strong>
                    <small>{leaf.title} · {meta.label}</small>
                  </span>
                  <span className={`knowledge-node-resource__status knowledge-node-resource__status--${slot.review_status}`}>
                    {standardReviewLabel(slot.review_status)}
                  </span>
                  <MaterialIcon name={expanded ? "expand_less" : "expand_more"} />
                </button>
                {expanded ? <pre className="knowledge-node-resource__preview">{previewText(slot)}</pre> : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
