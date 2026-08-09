import { useEffect, useMemo, useState } from "react";

import { getKnowledgeBaseDocuments, getKnowledgeGraph } from "../../api/courses";
import type { KnowledgeBaseDocument, KnowledgeGraphNode } from "../../api/types";
import { useCourseRoute } from "../CourseRouteProvider";
import { buildTeacherCourseHash } from "../../teacherRoutes";
import { MaterialIcon } from "../../shared";
import { KnowledgeDocumentPreviewDialog } from "./KnowledgeDocumentPreviewDialog";
import {
  defaultExpandedNodeIds,
  descendantNodeIds,
  flattenKnowledgeTree,
  toggleExpandedNode,
} from "./knowledgeTreeExpansion";

function nodeTree(
  node: KnowledgeGraphNode,
  activeId: string,
  expandedIds: ReadonlySet<string>,
  onSelect: (node: KnowledgeGraphNode) => void,
  onToggle: (node: KnowledgeGraphNode) => void,
) {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const expanded = expandedIds.has(node.id);
  return (
    <li key={node.id} className="knowledge-map__branch">
      <div className="knowledge-map__node-row">
        <button
          type="button"
          className="knowledge-map__node"
          aria-pressed={node.id === activeId}
          onClick={() => onSelect(node)}
        >
          <span className="knowledge-map__node-icon"><MaterialIcon name="hub" /></span>
          <span>{node.label}</span>
          {hasChildren && <small>{node.children!.length}</small>}
        </button>
        {hasChildren && (
          <button
            type="button"
            className="knowledge-tree__toggle knowledge-map__toggle"
            aria-label={`${expanded ? "收起" : "展开"}${node.label}`}
            aria-expanded={expanded}
            onClick={() => onToggle(node)}
          >
            <MaterialIcon name={expanded ? "expand_more" : "chevron_right"} />
          </button>
        )}
      </div>
      {hasChildren && expanded && (
        <ul className="knowledge-map__children">
          {node.children!.map((child) => nodeTree(child, activeId, expandedIds, onSelect, onToggle))}
        </ul>
      )}
    </li>
  );
}

function documentState(document: KnowledgeBaseDocument) {
  if (document.status === "ready") return null;
  if (document.status === "failed") return "处理失败";
  if (document.status === "partially_ready") return "部分可用";
  return "处理中";
}

export function KnowledgeStructureView({
  buildChatHref,
}: {
  buildChatHref?: (target: { scopeType: "course" | "knowledge_point"; scopeId?: string; scopeLabel: string }) => string;
} = {}) {
  const { courseId } = useCourseRoute();
  const [root, setRoot] = useState<KnowledgeGraphNode | null>(null);
  const [activeId, setActiveId] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [error, setError] = useState("");
  const [previewDocument, setPreviewDocument] = useState<KnowledgeBaseDocument | null>(null);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    setLoading(true);
    getKnowledgeGraph(courseId)
      .then((data) => {
        if (cancelled) return;
        setRoot(data.root);
        setActiveId(data.root.id);
        setExpandedIds(defaultExpandedNodeIds(data.root));
        setError("");
      })
      .catch(() => !cancelled && setError("知识图谱暂时无法加载，请稍后重试。"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [courseId]);

  const entries = useMemo(() => root ? flattenKnowledgeTree(root) : [], [root]);
  const activeNode = entries.find((item) => item.id === activeId) ?? entries[0] ?? null;
  const isRoot = Boolean(activeNode && activeNode.parentId === null);

  useEffect(() => {
    if (!courseId || !activeNode) return;
    let cancelled = false;
    setDocumentLoading(true);
    getKnowledgeBaseDocuments(courseId, isRoot
      ? { scopeType: "course", aggregate: true, libraryType: "course", limit: 200 }
      : {
          scopeType: "knowledge_point",
          scopeId: activeNode.id,
          includeDescendants: true,
          libraryType: "course",
          limit: 200,
        })
      .then((items) => !cancelled && setDocuments(items))
      .catch(() => !cancelled && setDocuments([]))
      .finally(() => !cancelled && setDocumentLoading(false));
    return () => { cancelled = true; };
  }, [activeNode, courseId, isRoot]);

  const chatTarget = activeNode ? (isRoot ? {
    scopeType: "course" as const,
    scopeLabel: activeNode.label,
  } : {
    scopeType: "knowledge_point" as const,
    scopeId: activeNode.id,
    scopeLabel: activeNode.label,
  }) : null;
  const chatHref = chatTarget
    ? buildChatHref?.(chatTarget) ?? buildTeacherCourseHash("ai", courseId, chatTarget)
    : buildTeacherCourseHash("ai", courseId);

  function toggleNode(node: KnowledgeGraphNode) {
    if (expandedIds.has(node.id) && descendantNodeIds(node).has(activeId)) {
      setActiveId(node.id);
    }
    setExpandedIds((current) => toggleExpandedNode(current, node));
  }

  if (loading) return <div className="knowledge-state">正在加载知识图谱…</div>;
  if (error || !root) return <div className="knowledge-state knowledge-state--error">{error || "课程尚未建立知识图谱。"}</div>;

  return (
    <section className="knowledge-graph-layout">
      <div className="knowledge-map">
        <header className="knowledge-map__header">
          <div>
            <span>课程结构</span>
            <h2>知识图谱</h2>
          </div>
          <p>点击节点查看它及全部子节点中的课程资料</p>
        </header>
        <div className="knowledge-map__viewport">
          <ul className="knowledge-map__root">
            {nodeTree(root, activeId, expandedIds, (node) => setActiveId(node.id), toggleNode)}
          </ul>
        </div>
      </div>

      <aside className="knowledge-node-panel">
        <span className="knowledge-node-panel__eyebrow">当前节点</span>
        <h2>{activeNode?.label}</h2>
        {activeNode?.data?.summary && <p className="knowledge-node-panel__summary">{activeNode.data.summary}</p>}
        <div className="knowledge-node-panel__title">
          <strong>节点资料</strong>
          <span>{documents.length} 份</span>
        </div>
        <div className="knowledge-node-panel__documents">
          {documentLoading ? (
            <p className="knowledge-node-panel__empty">正在读取资料…</p>
          ) : documents.length === 0 ? (
            <p className="knowledge-node-panel__empty">该节点及其子节点暂无资料</p>
          ) : documents.map((document) => {
              const state = documentState(document);
              return (
                <article key={document.id} className="knowledge-node-document" role="button" tabIndex={0} onClick={() => setPreviewDocument(document)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setPreviewDocument(document); }}>
                  <MaterialIcon name={document.type === "web" ? "language" : "description"} />
                  <div>
                    <strong>{document.display_name || document.source_title || document.name}</strong>
                    <small>{document.scope_id === activeNode?.id || isRoot ? "当前范围" : "来自子节点"}</small>
                  </div>
                  {state && <span>{state}</span>}
                </article>
              );
            })}
        </div>
        <a className="knowledge-node-panel__chat" href={chatHref}>
          <MaterialIcon name="auto_awesome" />
          和 AI 聊一聊
        </a>
      </aside>
      {previewDocument && courseId && <KnowledgeDocumentPreviewDialog courseId={courseId} document={previewDocument} onClose={() => setPreviewDocument(null)} />}
    </section>
  );
}
