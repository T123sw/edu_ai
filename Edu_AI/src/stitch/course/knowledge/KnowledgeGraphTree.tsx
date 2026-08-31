import type { KeyboardEvent } from "react";

import { MaterialIcon } from "../../shared";
import {
  ancestorNodeIds,
  visibleGraphNodeIds,
  type GraphReviewFilter,
  type GraphReviewModel,
} from "./courseKnowledgeGraphDraft";

type Props = {
  model: GraphReviewModel;
  selectedNodeId: string;
  expandedNodeIds: Set<string>;
  query: string;
  filter: GraphReviewFilter;
  onQueryChange: (query: string) => void;
  onExpandedChange: (ids: Set<string>) => void;
  onSelect: (nodeId: string) => void;
};

function nodeTypeLabel(type: string | undefined, childCount: number) {
  if (type === "course") return "课程";
  if (type === "knowledge_module") return "模块";
  if (type === "knowledge_unit") return "单元";
  return childCount ? "分组" : "知识点";
}

export function KnowledgeGraphTree({
  model,
  selectedNodeId,
  expandedNodeIds,
  query,
  filter,
  onQueryChange,
  onExpandedChange,
  onSelect,
}: Props) {
  const candidates = visibleGraphNodeIds(model, query, filter);
  const forcedOpen = Boolean(query.trim()) || filter !== "all";
  const visibleIds = candidates.filter((nodeId) => (
    forcedOpen
    || ancestorNodeIds(model, nodeId).every((ancestorId) => expandedNodeIds.has(ancestorId))
  ));

  function toggle(nodeId: string) {
    const next = new Set(expandedNodeIds);
    if (next.has(nodeId)) next.delete(nodeId);
    else next.add(nodeId);
    onExpandedChange(next);
  }

  function moveFocus(event: KeyboardEvent<HTMLDivElement>, nodeId: string) {
    const index = visibleIds.indexOf(nodeId);
    const current = model.nodesById.get(nodeId);
    let targetId: string | null = null;
    if (event.key === "ArrowDown") targetId = visibleIds[index + 1] || null;
    if (event.key === "ArrowUp") targetId = visibleIds[index - 1] || null;
    if (event.key === "ArrowRight") {
      if (current?.childCount && !expandedNodeIds.has(nodeId)) toggle(nodeId);
      else targetId = visibleIds[index + 1] || null;
    }
    if (event.key === "ArrowLeft") {
      if (current?.childCount && expandedNodeIds.has(nodeId)) toggle(nodeId);
      else targetId = current?.parentId || null;
    }
    if (event.key === "Enter" || event.key === " ") targetId = nodeId;
    if (!targetId) return;
    event.preventDefault();
    onSelect(targetId);
    requestAnimationFrame(() => document.getElementById(`graph-tree-${targetId}`)?.focus());
  }

  return (
    <section className="course-kb-graph__tree-pane course-kb-graph__pane" aria-label="知识图谱树">
      <div className="course-kb-graph__tree-tools">
        <label>
          <span>搜索节点</span>
          <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="输入节点名称" />
        </label>
        <div>
          <button type="button" onClick={() => onExpandedChange(new Set(model.orderedIds))}>全部展开</button>
          <button type="button" onClick={() => onExpandedChange(new Set())}>全部折叠</button>
        </div>
      </div>
      <div className="course-kb-graph__tree-list" role="tree" aria-label="课程知识图谱">
        {visibleIds.map((nodeId) => {
          const item = model.nodesById.get(nodeId)!;
          const expanded = forcedOpen || expandedNodeIds.has(nodeId);
          return (
            <div
              id={`graph-tree-${nodeId}`}
              key={nodeId}
              role="treeitem"
              tabIndex={nodeId === selectedNodeId ? 0 : -1}
              aria-level={item.depth}
              aria-selected={nodeId === selectedNodeId}
              aria-expanded={item.childCount ? expanded : undefined}
              className={`course-kb-graph__tree-row${nodeId === selectedNodeId ? " is-selected" : ""}`}
              style={{ paddingInlineStart: `${12 + (item.depth - 1) * 20}px` }}
              onClick={() => onSelect(nodeId)}
              onKeyDown={(event) => moveFocus(event, nodeId)}
            >
              {item.childCount ? (
                <button type="button" aria-label={expanded ? `折叠${item.label}` : `展开${item.label}`} onClick={(event) => { event.stopPropagation(); toggle(nodeId); }}>
                  <MaterialIcon name={expanded ? "expand_more" : "chevron_right"} />
                </button>
              ) : <span className="course-kb-graph__tree-spacer" />}
              <span className="course-kb-graph__tree-copy">
                <small>{nodeTypeLabel(item.node.data?.type, item.childCount)}</small>
                <strong>{item.label || "未命名节点"}</strong>
                <span>{item.childCount} 个直属子节点</span>
              </span>
              <span className="course-kb-graph__tree-tags">
                {item.isNew ? <em>新增</em> : null}
                {item.hasIssue ? <em className="is-warning">待完善</em> : null}
                {item.node.data?.review_state === "needs_parent" ? <em className="is-error">待选择父节点</em> : null}
                {item.isMapped ? <em className="is-mapped">教材已映射</em> : null}
              </span>
            </div>
          );
        })}
        {!visibleIds.length ? <p className="course-kb-graph__tree-empty">没有符合条件的节点</p> : null}
      </div>
    </section>
  );
}
