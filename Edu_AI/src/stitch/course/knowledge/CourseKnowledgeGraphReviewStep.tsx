import { useEffect, useMemo, useState } from "react";

import type {
  CourseKnowledgeBuildConfig,
  CourseKnowledgeTextbookInput,
  KnowledgeGraphNode,
} from "../../api/types";
import { MaterialIcon } from "../../shared";
import {
  addGraphChild,
  graphDraftEqual,
  graphDraftStats,
  graphNodeOptions,
  moveGraphNode,
  moveGraphSibling,
  removeGraphNode,
  updateGraphNode,
} from "./courseKnowledgeGraphDraft";

type Props = {
  root: KnowledgeGraphNode;
  savedRoot: KnowledgeGraphNode;
  config: CourseKnowledgeBuildConfig;
  textbooks: CourseKnowledgeTextbookInput[];
  busy: boolean;
  onChange: (root: KnowledgeGraphNode) => void;
  onBack: () => void;
  onSave: (root: KnowledgeGraphNode) => Promise<KnowledgeGraphNode>;
  onRegenerate: (moduleId?: string) => void;
  onConfirmAndStart: (root: KnowledgeGraphNode) => void;
};

type EditorProps = {
  node: KnowledgeGraphNode;
  depth: number;
  root: KnowledgeGraphNode;
  maxDepth: number;
  busy: boolean;
  onChange: (root: KnowledgeGraphNode) => void;
  onRegenerate: (moduleId: string) => void;
};

function NodeEditor({ node, depth, root, maxDepth, busy, onChange, onRegenerate }: EditorProps) {
  const options = graphNodeOptions(root);
  const current = options.find((item) => item.id === node.id);
  const parentCandidates = options.filter((item) => item.depth === depth - 1);
  const childCount = node.children?.length || 0;

  return (
    <li className={`course-kb-graph__node depth-${depth}`}>
      <div className="course-kb-graph__node-card">
        <div className="course-kb-graph__node-heading">
          <span>{depth === 1 ? "课程" : childCount ? (depth === 2 ? "模块" : "单元") : "知识点"}</span>
          <input
            aria-label={`${node.label || "未命名节点"}名称`}
            value={node.label}
            disabled={busy}
            onChange={(event) => onChange(updateGraphNode(root, node.id, { label: event.target.value }))}
          />
        </div>
        <textarea
          aria-label={`${node.label || "未命名节点"}说明`}
          value={node.data?.summary || ""}
          disabled={busy}
          rows={2}
          placeholder="说明这个节点覆盖的课程内容"
          onChange={(event) => onChange(updateGraphNode(root, node.id, { summary: event.target.value }))}
        />
        <div className="course-kb-graph__node-meta">
          <span>{childCount} 个直属子节点</span>
          {(node.data?.source_outline_refs || []).length ? (
            <span>教材映射：{node.data?.source_outline_refs?.join("、")}</span>
          ) : null}
        </div>
        <div className="course-kb-graph__node-actions">
          {depth > 1 ? (
            <label>
              父节点
              <select
                aria-label={`${node.label}父节点`}
                value={current?.parentId || ""}
                disabled={busy}
                onChange={(event) => onChange(moveGraphNode(root, node.id, event.target.value))}
              >
                {parentCandidates.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
          ) : null}
          {depth < maxDepth ? (
            <button type="button" disabled={busy} onClick={() => onChange(addGraphChild(root, node.id, maxDepth).root)}>
              <MaterialIcon name="add" />添加子节点
            </button>
          ) : null}
          {depth === 2 ? (
            <button type="button" disabled={busy} onClick={() => onRegenerate(node.id)}>
              <MaterialIcon name="refresh" />重新生成此模块
            </button>
          ) : null}
          {depth > 1 ? (
            <>
              <button type="button" aria-label={`${node.label}上移`} disabled={busy} onClick={() => onChange(moveGraphSibling(root, node.id, -1))}>
                <MaterialIcon name="arrow_upward" />
              </button>
              <button type="button" aria-label={`${node.label}下移`} disabled={busy} onClick={() => onChange(moveGraphSibling(root, node.id, 1))}>
                <MaterialIcon name="arrow_downward" />
              </button>
              <button type="button" className="is-danger" disabled={busy} onClick={() => onChange(removeGraphNode(root, node.id))}>
                <MaterialIcon name="delete" />删除
              </button>
            </>
          ) : null}
        </div>
      </div>
      {childCount ? (
        <ul>
          {node.children!.map((child) => (
            <NodeEditor
              key={child.id}
              node={child}
              depth={depth + 1}
              root={root}
              maxDepth={maxDepth}
              busy={busy}
              onChange={onChange}
              onRegenerate={onRegenerate}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function CourseKnowledgeGraphReviewStep({
  root,
  savedRoot,
  config,
  textbooks,
  busy,
  onChange,
  onBack,
  onSave,
  onRegenerate,
  onConfirmAndStart,
}: Props) {
  const [impactAccepted, setImpactAccepted] = useState(false);
  const stats = useMemo(() => graphDraftStats(root), [root]);
  const missingContentCount = useMemo(() => {
    let count = 0;
    function visit(node: KnowledgeGraphNode) {
      if (!node.label.trim() || !(node.data?.summary || "").trim()) count += 1;
      (node.children || []).forEach(visit);
    }
    visit(root);
    return count;
  }, [root]);
  const dirty = !graphDraftEqual(root, savedRoot);
  const targetLeaves = config.target_module_count * config.target_points_per_module;
  const readyTextbooks = textbooks.filter((item) => item.status === "ready");
  const localWarnings = [
    stats.maxDepth !== config.graph_depth ? `当前深度 ${stats.maxDepth}，目标深度 ${config.graph_depth}` : "",
    stats.moduleCount < Math.ceil(config.target_module_count * .8)
      || stats.moduleCount > Math.floor(config.target_module_count * 1.2)
      ? `当前模块数 ${stats.moduleCount} 与目标 ${config.target_module_count} 差异较大`
      : "",
    stats.leafCount < Math.ceil(targetLeaves * .8)
      || stats.leafCount > Math.floor(targetLeaves * 1.2)
      ? `当前知识点数 ${stats.leafCount} 与目标 ${targetLeaves} 差异较大`
      : "",
    missingContentCount ? `${missingContentCount} 个节点缺少名称或说明` : "",
  ].filter(Boolean);

  useEffect(() => setImpactAccepted(false), [root]);

  function requestRegenerate(moduleId?: string) {
    if (dirty && !window.confirm("重新生成会丢弃尚未保存的图谱修改，是否继续？")) return;
    onRegenerate(moduleId);
  }

  return (
    <section className="course-kb-wizard__step course-kb-graph" aria-labelledby="kb-graph-heading">
      <div className="course-kb-wizard__step-heading">
        <div><span>第三步</span><h3 id="kb-graph-heading">审核知识图谱</h3></div>
        <p>这里的结构将决定后续网络检索、教材拆分和资料归档范围。</p>
      </div>

      <div className="course-kb-graph__stats" aria-label="图谱规模对照">
        <span><small>层级</small><strong>{stats.maxDepth} / {config.graph_depth}</strong></span>
        <span><small>模块</small><strong>{stats.moduleCount} / {config.target_module_count}</strong></span>
        <span><small>知识点</small><strong>{stats.leafCount} / {targetLeaves}</strong></span>
        <span><small>全部节点</small><strong>{stats.nodeCount}</strong></span>
        <span><small>教材映射</small><strong>{stats.mappedOutlineCount}</strong></span>
      </div>

      {readyTextbooks.length ? (
        <div className="course-kb-graph__textbook-summary">
          <MaterialIcon name="menu_book" />
          <div>
            <strong>已参考 {readyTextbooks.length} 份教材生成</strong>
            <span>
              共识别 {readyTextbooks.reduce((sum, item) => sum + (item.parse_result?.chapter_count || 0), 0)} 个章节；
              已映射 {stats.mappedOutlineCount} 项，明确不映射 {stats.unmappedOutlineCount} 项。
            </span>
          </div>
        </div>
      ) : (
        <div className="course-kb-graph__textbook-summary">
          <MaterialIcon name="info" /><div><strong>本次未使用教材</strong><span>图谱完全由模型结合课程信息生成。</span></div>
        </div>
      )}

      {localWarnings.length ? (
        <div className="course-kb-wizard__validation" role="status">
          {localWarnings.map((warning) => <div key={warning}>{warning}</div>)}
        </div>
      ) : null}

      <div className="course-kb-graph__toolbar">
        <button type="button" className="course-kb-wizard__secondary" disabled={busy || !dirty} onClick={() => onChange(savedRoot)}>
          撤销未保存修改
        </button>
        <button type="button" className="course-kb-wizard__secondary" disabled={busy} onClick={() => requestRegenerate()}>
          <MaterialIcon name="refresh" />重新生成全部图谱
        </button>
        <button type="button" className="course-kb-wizard__secondary" disabled={busy || !dirty} onClick={() => void onSave(root)}>
          保存草案
        </button>
      </div>

      <ul className="course-kb-graph__tree">
        <NodeEditor node={root} depth={1} root={root} maxDepth={config.graph_depth} busy={busy} onChange={onChange} onRegenerate={(moduleId) => requestRegenerate(moduleId)} />
      </ul>

      <div className="course-kb-graph__confirm">
        <label>
          <input type="checkbox" checked={impactAccepted} disabled={busy} onChange={(event) => setImpactAccepted(event.target.checked)} />
          我已审核图谱。确认后将锁定当前修订并开始网络检索、教材拆分和正式入库；之后修改图谱需要重新确认。
        </label>
      </div>
      <footer className="course-kb-wizard__footer is-split">
        <button type="button" className="course-kb-wizard__secondary" disabled={busy} onClick={onBack}>返回教材步骤</button>
        <button type="button" className="course-kb-wizard__primary" disabled={busy || !impactAccepted} onClick={() => onConfirmAndStart(root)}>
          {busy ? "正在处理…" : "确认图谱并开始构建"}
        </button>
      </footer>
    </section>
  );
}
