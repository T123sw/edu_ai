import { useEffect, useMemo, useRef, useState } from "react";

import { getKnowledgeBaseDocuments, getKnowledgeGraph, uploadKnowledgeBaseDocument } from "../../api/courses";
import type { KnowledgeBaseDocument, KnowledgeGraphNode } from "../../api/types";
import { registerCreatedJob } from "../../../jobs/jobStore";
import { MaterialIcon } from "../../shared";
import { canCourse } from "../coursePermissions";
import { useCourseRoute } from "../CourseRouteProvider";
import {
  defaultExpandedNodeIds,
  descendantNodeIds,
  flattenKnowledgeTree,
  toggleExpandedNode,
  visibleKnowledgeTree,
} from "./knowledgeTreeExpansion";

function statusLabel(status: KnowledgeBaseDocument["status"]) {
  if (status === "failed") return "处理失败";
  if (status === "partially_ready") return "部分可用";
  if (status === "ready") return "";
  return "处理中";
}

export function KnowledgeDocumentsView() {
  const { courseId, courseRole } = useCourseRoute();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const canUpload = canCourse(courseRole, "edit");
  const [root, setRoot] = useState<KnowledgeGraphNode | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (!courseId) return;
    getKnowledgeGraph(courseId)
      .then((data) => {
        setRoot(data.root);
        setSelectedNodeId((current) => current || data.root.id);
        setExpandedIds(defaultExpandedNodeIds(data.root));
      })
      .catch(() => setError("知识图谱暂时无法加载，请稍后重试。"));
  }, [courseId]);

  const nodes = useMemo(() => root ? flattenKnowledgeTree(root) : [], [root]);
  const visibleNodes = useMemo(
    () => root ? visibleKnowledgeTree(root, expandedIds) : [],
    [expandedIds, root],
  );
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0] ?? null;
  const isRoot = Boolean(selectedNode && selectedNode.parentId === null);
  const isLeaf = Boolean(selectedNode && (selectedNode.children?.length ?? 0) === 0);

  useEffect(() => {
    if (!courseId || !selectedNode) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    getKnowledgeBaseDocuments(courseId, isRoot
      ? { scopeType: "course", aggregate: true, libraryType: "course", limit: 200, sort: "created_desc" }
      : {
          scopeType: "knowledge_point",
          scopeId: selectedNode.id,
          includeDescendants: true,
          libraryType: "course",
          limit: 200,
          sort: "created_desc",
        })
      .then((items) => !cancelled && setDocuments(items))
      .catch(() => !cancelled && setError("课程资料暂时无法读取，请稍后重试。"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [courseId, isRoot, reload, selectedNode]);

  async function upload(files: FileList | null) {
    if (!files?.length || !courseId || !selectedNode || !canUpload) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const result = await uploadKnowledgeBaseDocument(courseId, file, isRoot
          ? { scopeType: "course", libraryType: "course" }
          : { scopeType: "knowledge_point", scopeId: selectedNode.id, libraryType: "course" });
        registerCreatedJob(result.job);
      }
      setReload((value) => value + 1);
    } catch {
      setError("资料上传失败，请检查文件后重试。");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function toggleNode(node: KnowledgeGraphNode) {
    if (expandedIds.has(node.id) && descendantNodeIds(node).has(selectedNodeId)) {
      setSelectedNodeId(node.id);
    }
    setExpandedIds((current) => toggleExpandedNode(current, node));
  }

  return (
    <section className="knowledge-library">
      <aside className="knowledge-library__nodes">
        <div className="knowledge-library__heading">
          <span>归档位置</span>
          <h2>选择知识节点</h2>
        </div>
        <div className="knowledge-library__node-list">
          {visibleNodes.map((node) => {
            const hasChildren = (node.children?.length ?? 0) > 0;
            const expanded = expandedIds.has(node.id);
            return (
              <div
                key={node.id}
                className="knowledge-library__node-row"
                style={{ paddingLeft: `${6 + node.depth * 18}px` }}
              >
                <button
                  type="button"
                  className="knowledge-library__node-select"
                  aria-pressed={node.id === selectedNode?.id}
                  onClick={() => setSelectedNodeId(node.id)}
                >
                  <MaterialIcon name={hasChildren ? "account_tree" : "circle"} />
                  <span>{node.label}</span>
                  {!hasChildren && <small>叶子</small>}
                </button>
                {hasChildren && (
                  <button
                    type="button"
                    className="knowledge-tree__toggle knowledge-library__node-toggle"
                    aria-label={`${expanded ? "收起" : "展开"}${node.label}`}
                    aria-expanded={expanded}
                    onClick={() => toggleNode(node)}
                  >
                    <MaterialIcon name={expanded ? "expand_more" : "chevron_right"} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </aside>

      <div className="knowledge-library__content">
        <header className="knowledge-library__toolbar">
          <div>
            <span>课程知识库</span>
            <h2>{selectedNode?.label || "课程资料"}</h2>
            <p>{isLeaf ? "资料将直接归档到该叶子节点。" : "这里同时展示该节点及所有子节点的资料；上传内容归档到当前节点。"}</p>
          </div>
          {canUpload && (
            <>
              <input ref={fileRef} type="file" multiple hidden onChange={(event) => void upload(event.target.files)} />
              <button type="button" disabled={uploading || !selectedNode} onClick={() => fileRef.current?.click()}>
                <MaterialIcon name="upload_file" />
                {uploading ? "正在上传…" : "上传资料"}
              </button>
            </>
          )}
        </header>
        {error && <div className="knowledge-library__error">{error}</div>}
        <div className="knowledge-library__documents">
          {loading ? (
            <p className="knowledge-library__empty">正在读取资料…</p>
          ) : documents.length === 0 ? (
            <p className="knowledge-library__empty">当前节点暂无资料</p>
          ) : documents.map((document) => {
              const status = statusLabel(document.status);
              return (
                <article key={document.id} className="knowledge-library-document">
                  <span className="knowledge-library-document__icon"><MaterialIcon name={document.type === "web" ? "language" : "description"} /></span>
                  <div>
                    <strong>{document.name}</strong>
                    <small>{document.scope_id === selectedNode?.id || isRoot ? "当前节点" : "子节点资料"} · {new Date(document.created_at).toLocaleString("zh-CN")}</small>
                  </div>
                  {status && <span className={`knowledge-library-document__status knowledge-library-document__status--${document.status}`}>{status}</span>}
                </article>
              );
            })}
        </div>
      </div>
    </section>
  );
}
