import { useEffect, useMemo, useState } from "react";

import type {
  CourseKnowledgeBuildConfig,
  CourseKnowledgeTextbookInput,
  KnowledgeGraphNode,
} from "../../api/types";
import { MaterialIcon } from "../../shared";
import {
  ancestorNodeIds,
  buildGraphReviewModel,
  findGraphNode,
  graphDraftEqual,
  graphDraftStats,
  type GraphReviewFilter,
} from "./courseKnowledgeGraphDraft";
import { KnowledgeGraphNodeEditor } from "./KnowledgeGraphNodeEditor";
import { KnowledgeGraphReviewActions } from "./KnowledgeGraphReviewActions";
import { KnowledgeGraphReviewSummary } from "./KnowledgeGraphReviewSummary";
import { KnowledgeGraphTree } from "./KnowledgeGraphTree";

type Props = {
  root: KnowledgeGraphNode;
  savedRoot: KnowledgeGraphNode;
  baselineRoot: KnowledgeGraphNode | null;
  config: CourseKnowledgeBuildConfig;
  textbooks: CourseKnowledgeTextbookInput[];
  busy: boolean;
  onChange: (root: KnowledgeGraphNode) => void;
  onBack: () => void;
  onSave: (root: KnowledgeGraphNode) => Promise<KnowledgeGraphNode>;
  onRegenerate: (moduleId?: string) => void;
  onConfirmAndStart: (root: KnowledgeGraphNode) => void;
};

export function CourseKnowledgeGraphReviewStep({
  root,
  savedRoot,
  baselineRoot,
  config,
  textbooks,
  busy,
  onChange,
  onBack,
  onSave,
  onRegenerate,
  onConfirmAndStart,
}: Props) {
  const model = useMemo(() => buildGraphReviewModel(root, baselineRoot), [root, baselineRoot]);
  const stats = useMemo(() => graphDraftStats(root), [root]);
  const [selectedNodeId, setSelectedNodeId] = useState(model.initialSelectedNodeId);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
    () => new Set([root.id, ...(root.children || []).map((node) => node.id)]),
  );
  const [treeQuery, setTreeQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<GraphReviewFilter>("all");
  const [mobilePane, setMobilePane] = useState<"tree" | "editor">("tree");
  const [impactAccepted, setImpactAccepted] = useState(false);
  const dirty = !graphDraftEqual(root, savedRoot);
  const selectedNode = findGraphNode(root, selectedNodeId) || root;
  const readyTextbooks = textbooks.filter((item) => item.status === "ready");
  const targetLeaves = config.target_module_count * config.target_points_per_module;
  const scaleWarnings = [
    stats.maxDepth !== config.graph_depth ? `当前深度 ${stats.maxDepth}，目标深度 ${config.graph_depth}` : "",
    stats.moduleCount < Math.ceil(config.target_module_count * .8)
      || stats.moduleCount > Math.floor(config.target_module_count * 1.2)
      ? `当前模块数 ${stats.moduleCount} 与目标 ${config.target_module_count} 差异较大`
      : "",
    stats.leafCount < Math.ceil(targetLeaves * .8)
      || stats.leafCount > Math.floor(targetLeaves * 1.2)
      ? `当前知识点数 ${stats.leafCount} 与目标 ${targetLeaves} 差异较大`
      : "",
  ].filter(Boolean);

  useEffect(() => {
    setImpactAccepted(false);
    if (!model.nodesById.has(selectedNodeId)) setSelectedNodeId(model.initialSelectedNodeId);
  }, [model, root, selectedNodeId]);

  function requestRegenerate(moduleId?: string) {
    if (dirty && !window.confirm("重新生成会丢弃尚未保存的图谱修改，是否继续？")) return;
    onRegenerate(moduleId);
  }

  function selectNode(nodeId: string) {
    setSelectedNodeId(nodeId);
    setMobilePane("editor");
  }

  function selectIssue(nodeId: string) {
    setExpandedNodeIds((current) => new Set([...current, ...ancestorNodeIds(model, nodeId)]));
    selectNode(nodeId);
    requestAnimationFrame(() => document.getElementById("graph-current-node")?.focus());
  }

  return (
    <section className="course-kb-wizard__step course-kb-graph" aria-labelledby="kb-graph-heading">
      <div className="course-kb-wizard__step-heading">
        <div><span>第三步</span><h3 id="kb-graph-heading">审核知识图谱</h3></div>
        <p>从左侧选择节点，只在右侧编辑当前节点；顶部会持续提示新增内容和待完善问题。</p>
      </div>

      <KnowledgeGraphReviewSummary
        stats={stats}
        newCount={[...model.nodesById.values()].filter((item) => item.isNew).length}
        issues={model.issues}
        activeFilter={activeFilter}
        dirty={dirty}
        onFilterChange={setActiveFilter}
        onSelectIssue={selectIssue}
      />

      <div className="course-kb-graph__context-row">
        <div className="course-kb-graph__textbook-summary">
          <MaterialIcon name={readyTextbooks.length ? "menu_book" : "info"} />
          <div>
            <strong>{readyTextbooks.length ? `已参考 ${readyTextbooks.length} 份教材生成` : "本次未使用教材"}</strong>
            <span>
              {readyTextbooks.length
                ? `已映射 ${stats.mappedOutlineCount} 项，明确不映射 ${stats.unmappedOutlineCount} 项。`
                : "图谱由模型结合课程信息和现有知识结构生成。"}
            </span>
          </div>
        </div>
        <div className="course-kb-graph__toolbar">
          <button type="button" className="course-kb-wizard__secondary" disabled={busy || !dirty} onClick={() => onChange(savedRoot)}>
            撤销未保存修改
          </button>
          <button type="button" className="course-kb-wizard__secondary" disabled={busy} onClick={() => requestRegenerate()}>
            <MaterialIcon name="refresh" />重新生成全部图谱
          </button>
        </div>
      </div>

      {scaleWarnings.length ? (
        <div className="course-kb-wizard__validation" role="status">
          {scaleWarnings.map((warning) => <div key={warning}>{warning}</div>)}
        </div>
      ) : null}

      <div className="course-kb-graph__mobile-tabs" role="tablist" aria-label="图谱审核视图">
        <button type="button" role="tab" aria-selected={mobilePane === "tree"} onClick={() => setMobilePane("tree")}>图谱</button>
        <button type="button" role="tab" aria-selected={mobilePane === "editor"} onClick={() => setMobilePane("editor")}>节点详情</button>
      </div>

      <div className="course-kb-graph__workspace">
        <div className={mobilePane === "tree" ? "is-mobile-active" : "is-mobile-hidden"}>
          <KnowledgeGraphTree
            model={model}
            selectedNodeId={selectedNodeId}
            expandedNodeIds={expandedNodeIds}
            query={treeQuery}
            filter={activeFilter}
            onQueryChange={setTreeQuery}
            onExpandedChange={setExpandedNodeIds}
            onSelect={selectNode}
          />
        </div>
        <div className={mobilePane === "editor" ? "is-mobile-active" : "is-mobile-hidden"}>
          <KnowledgeGraphNodeEditor
            node={selectedNode}
            root={root}
            baseline={baselineRoot}
            maxDepth={config.graph_depth}
            busy={busy}
            onChange={onChange}
            onRegenerate={(moduleId) => requestRegenerate(moduleId)}
          />
        </div>
      </div>

      <KnowledgeGraphReviewActions
        busy={busy}
        dirty={dirty}
        impactAccepted={impactAccepted}
        issueCount={model.issues.length}
        onImpactAcceptedChange={setImpactAccepted}
        onBack={onBack}
        onSave={() => void onSave(root)}
        onConfirm={() => onConfirmAndStart(root)}
      />
    </section>
  );
}
