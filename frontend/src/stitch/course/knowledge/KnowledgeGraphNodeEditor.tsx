import type { KnowledgeGraphNode } from "../../api/types";
import { MaterialIcon } from "../../shared";
import {
  addGraphChild,
  canEditGraphNodeStructure,
  graphNodeOptions,
  moveGraphNode,
  moveGraphSibling,
  removeGraphNode,
  updateGraphNode,
} from "./courseKnowledgeGraphDraft";

type Props = {
  node: KnowledgeGraphNode;
  root: KnowledgeGraphNode;
  baseline: KnowledgeGraphNode | null;
  maxDepth: number;
  busy: boolean;
  onChange: (root: KnowledgeGraphNode) => void;
  onRegenerate: (moduleId: string) => void;
};

function typeLabel(value: string | undefined) {
  return {
    course: "课程",
    knowledge_module: "模块",
    knowledge_unit: "单元",
    knowledge_point: "知识点",
  }[value || ""] || "知识节点";
}

export function KnowledgeGraphNodeEditor({
  node,
  root,
  baseline,
  maxDepth,
  busy,
  onChange,
  onRegenerate,
}: Props) {
  const options = graphNodeOptions(root);
  const current = options.find((item) => item.id === node.id);
  const depth = current?.depth || 1;
  const parentCandidates = options.filter((item) => item.depth === depth - 1);
  const structureEditable = canEditGraphNodeStructure(node.id, baseline);
  const refs = node.data?.source_outline_refs || [];
  const documents = node.data?.document_ids || [];

  return (
    <section className="course-kb-graph__editor-pane course-kb-graph__pane" aria-labelledby="graph-current-node">
      <header className="course-kb-graph__editor-heading">
        <div><span>{typeLabel(node.data?.type)}</span><h4 id="graph-current-node" tabIndex={-1}>当前节点</h4></div>
        <strong>{node.label || "未命名节点"}</strong>
      </header>

      {!structureEditable ? (
        <div className="course-kb-graph__protected" role="note">
          <MaterialIcon name="lock" />
          <span>现有节点的名称、类型和位置受保护；可以补充说明和教材映射。</span>
        </div>
      ) : null}

      <div className="course-kb-graph__editor-fields">
        <label>
          节点名称
          <input
            aria-label={`${node.label || "未命名节点"}名称`}
            value={node.label}
            disabled={busy || !structureEditable}
            onChange={(event) => onChange(updateGraphNode(root, node.id, { label: event.target.value }))}
          />
        </label>
        <label>
          节点类型
          <input value={typeLabel(node.data?.type)} disabled />
        </label>
        <label className="is-wide">
          内容说明
          <textarea
            aria-label={`${node.label || "未命名节点"}说明`}
            value={node.data?.summary || ""}
            disabled={busy}
            rows={7}
            placeholder="说明这个节点覆盖的课程内容"
            onChange={(event) => onChange(updateGraphNode(root, node.id, { summary: event.target.value }))}
          />
        </label>
        {depth > 1 ? (
          <label>
            父节点
            <select
              aria-label={`${node.label || "未命名节点"}父节点`}
              value={current?.parentId || ""}
              disabled={busy || !structureEditable}
              onChange={(event) => onChange(moveGraphNode(root, node.id, event.target.value))}
            >
              {parentCandidates.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
        ) : null}
        <label className="is-wide">
          教材映射
          <textarea
            aria-label={`${node.label || "未命名节点"}教材映射`}
            value={refs.join("\n")}
            disabled={busy}
            rows={3}
            placeholder="每行填写一个教材目录或引用"
            onChange={(event) => onChange(updateGraphNode(root, node.id, {
              sourceOutlineRefs: event.target.value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean),
            }))}
          />
        </label>
      </div>

      <section className="course-kb-graph__node-context" aria-label="节点上下文">
        <div><strong>直属子节点</strong><span>{node.children?.length || 0} 个</span></div>
        <div><strong>来源文档</strong><span>{documents.length ? documents.join("、") : "暂未关联来源文档"}</span></div>
      </section>

      <details className="course-kb-graph__more-actions">
        <summary>更多操作</summary>
        <div>
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
          {depth > 1 && structureEditable ? (
            <>
              <button type="button" aria-label={`${node.label}上移`} disabled={busy} onClick={() => onChange(moveGraphSibling(root, node.id, -1))}>
                <MaterialIcon name="arrow_upward" />上移
              </button>
              <button type="button" aria-label={`${node.label}下移`} disabled={busy} onClick={() => onChange(moveGraphSibling(root, node.id, 1))}>
                <MaterialIcon name="arrow_downward" />下移
              </button>
              <button
                type="button"
                className="is-danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`确认删除新增节点“${node.label}”？`)) onChange(removeGraphNode(root, node.id));
                }}
              >
                <MaterialIcon name="delete" />删除新增节点
              </button>
            </>
          ) : null}
        </div>
      </details>
    </section>
  );
}
