import { useCallback, useEffect, useMemo, useState } from "react";

import { getStandardResources, reviewStandardResource } from "../../api/standardResources";
import type { StandardResourceLeaf, StandardResourceSlot } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { KnowledgeNodeResourceDialog } from "./KnowledgeNodeResourceDialog";
import {
  canApproveStandardResource,
  getStandardResourceDetailTarget,
  STANDARD_RESOURCE_KIND_META,
  standardResourceLeavesForKnowledgeScope,
  standardReviewLabel,
} from "./standardLearningResourcesPresentation";

export function KnowledgeNodeCourseResources({
  courseId,
  nodeLabel,
  scopeNodeIds,
  canManage,
}: {
  courseId: string;
  nodeLabel: string;
  scopeNodeIds: ReadonlySet<string>;
  canManage: boolean;
}) {
  const [leaves, setLeaves] = useState<StandardResourceLeaf[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [selectedResource, setSelectedResource] = useState<{
    leaf: StandardResourceLeaf;
    slot: StandardResourceSlot;
  } | null>(null);

  const loadCatalog = useCallback(async () => {
    if (!courseId) return;
    setLoading(true);
    try {
      const catalog = await getStandardResources(courseId);
      setLeaves(catalog.leaves);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "课程资料暂时无法读取");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    if (!courseId) return;
    const handleMaterialUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ courseId?: string }>).detail;
      if (!detail?.courseId || detail.courseId === courseId) void loadCatalog();
    };
    void loadCatalog();
    window.addEventListener("edu-ai:course-material-updated", handleMaterialUpdated);
    return () => window.removeEventListener("edu-ai:course-material-updated", handleMaterialUpdated);
  }, [courseId, loadCatalog]);

  const scopedLeaves = useMemo(
    () => standardResourceLeavesForKnowledgeScope(leaves, scopeNodeIds),
    [leaves, scopeNodeIds],
  );
  const resources = scopedLeaves.flatMap((leaf) => leaf.slots
    .filter((slot) => Boolean(slot.resource))
    .map((slot) => ({ leaf, slot })));

  function openResource(leaf: StandardResourceLeaf, slot: StandardResourceSlot) {
    const target = getStandardResourceDetailTarget(courseId, slot);
    if (target.kind === "route") {
      window.location.hash = target.href;
      return;
    }
    setSelectedResource({ leaf, slot });
  }

  async function approve(slot: StandardResourceSlot) {
    if (!canApproveStandardResource(canManage, slot) || working) return;
    setWorking(true);
    setError("");
    try {
      await reviewStandardResource(courseId, slot.material_id, "approved");
      setSelectedResource(null);
      await loadCatalog();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "审核操作失败，请稍后重试");
    } finally {
      setWorking(false);
    }
  }

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
            const canApprove = canApproveStandardResource(canManage, slot);
            return (
              <article key={`${leaf.leaf_id}:${slot.material_id}`} className="knowledge-node-resource">
                <button
                  type="button"
                  className="knowledge-node-resource__summary"
                  onClick={() => openResource(leaf, slot)}
                >
                  <span className="knowledge-node-resource__icon"><MaterialIcon name={meta.icon} /></span>
                  <span className="knowledge-node-resource__copy">
                    <strong>{String(slot.resource?.title || `${leaf.title}${meta.label}`)}</strong>
                    <small>{leaf.title} · {meta.label}</small>
                  </span>
                  <span className={`knowledge-node-resource__status knowledge-node-resource__status--${slot.review_status}`}>
                    {standardReviewLabel(slot.review_status)}
                  </span>
                  <MaterialIcon name={slot.standard_kind === "classroom" ? "play_circle" : "visibility"} />
                </button>
                {canApprove && slot.standard_kind === "classroom" ? (
                  <div className="knowledge-node-resource__actions">
                    <button
                      type="button"
                      className="knowledge-node-resource__approve"
                      disabled={working}
                      onClick={(event) => {
                        event.stopPropagation();
                        void approve(slot);
                      }}
                    >
                      <MaterialIcon name="check_circle" />
                      通过审核
                    </button>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
      {selectedResource ? (
        <KnowledgeNodeResourceDialog
          leafTitle={selectedResource.leaf.title}
          slot={selectedResource.slot}
          canManage={canManage}
          busy={working}
          onApprove={() => void approve(selectedResource.slot)}
          onClose={() => setSelectedResource(null)}
        />
      ) : null}
    </section>
  );
}
