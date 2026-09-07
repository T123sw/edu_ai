import { Dropdown, Input, Modal } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import { renameKnowledgeBaseDocument, deleteKnowledgeBaseDocument, getKnowledgeBaseDocuments, getKnowledgeGraph, uploadKnowledgeBaseDocument } from "../../api/courses";
import type { KnowledgeBaseDocument, KnowledgeGraphNode } from "../../api/types";
import { registerCreatedJob } from "../../../jobs/jobStore";
import { MaterialIcon } from "../../shared";
import { canCourse } from "../coursePermissions";
import { useCourseRoute } from "../CourseRouteProvider";
import { KnowledgeDocumentPreviewDialog } from "./KnowledgeDocumentPreviewDialog";
import { CourseKnowledgeBuildCard } from "./CourseKnowledgeBuildCard";
import "./KnowledgeDocumentsView.css";
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

export function KnowledgeDocumentsView({ readOnly = false }: { readOnly?: boolean } = {}) {
  const { courseId, courseRole } = useCourseRoute();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const canUpload = !readOnly && canCourse(courseRole, "edit");
  const [root, setRoot] = useState<KnowledgeGraphNode | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [previewDocument, setPreviewDocument] = useState<KnowledgeBaseDocument | null>(null);
  const [editingDocument, setEditingDocument] = useState<KnowledgeBaseDocument | null>(null);
  const [editName, setEditName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [editError, setEditError] = useState("");
  const actionHandledRef = useRef(false);
  const requestedAction = typeof window === "undefined"
    ? null
    : new URLSearchParams(window.location.hash.split("?")[1] || "").get("action");

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
  const visibleDocuments = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return documents.filter((document) =>
      (document.display_name || document.source_title || document.name).toLocaleLowerCase().includes(query),
    );
  }, [documents, search]);

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

  useEffect(() => {
    const handleUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ courseId?: string }>).detail;
      if (!detail?.courseId || detail.courseId === courseId) setReload((value) => value + 1);
    };
    window.addEventListener("edu-ai:knowledge-document-updated", handleUpdated);
    return () => window.removeEventListener("edu-ai:knowledge-document-updated", handleUpdated);
  }, [courseId]);

  useEffect(() => {
    if (requestedAction !== "upload" || !canUpload || !selectedNode || actionHandledRef.current) return;
    actionHandledRef.current = true;
    fileRef.current?.click();
  }, [canUpload, requestedAction, selectedNode]);

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

  async function deleteDocument(document: KnowledgeBaseDocument) {
    if (!courseId || !canUpload || deletingDocumentId) return;
    const title = document.display_name || document.source_title || document.name;
    if (!window.confirm(`确认删除当前节点下的文档“${title}”？文档文件和检索索引会被永久删除，知识图谱结构不会改变。`)) return;
    setDeletingDocumentId(document.id);
    setError("");
    try {
      await deleteKnowledgeBaseDocument(courseId, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      if (previewDocument?.id === document.id) setPreviewDocument(null);
      window.dispatchEvent(new CustomEvent("edu-ai:knowledge-document-updated", { detail: { courseId } }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除文档失败，请稍后重试。");
    } finally {
      setDeletingDocumentId(null);
    }
  }

  async function saveDocumentName() {
    if (!courseId || !editingDocument || !canUpload || savingName) return;
    if (!editName.trim()) { setEditError("请输入资料名称"); return; }
    setSavingName(true);
    setEditError("");
    try {
      const updated = await renameKnowledgeBaseDocument(courseId, editingDocument.id, editName.trim());
      setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditingDocument(null);
      window.dispatchEvent(new CustomEvent("edu-ai:knowledge-document-updated", { detail: { courseId } }));
    } catch (reason) {
      setEditError(reason instanceof Error ? reason.message : "修改失败，请稍后重试。");
    } finally { setSavingName(false); }
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
          <span>知识目录</span>
          <h2>{root?.label || "课程知识目录"}</h2>
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
                  aria-expanded={hasChildren ? expanded : undefined}
                  onClick={() => {
                    setSelectedNodeId(node.id);
                    setSearch("");
                    if (hasChildren) toggleNode(node);
                  }}
                >
                  <MaterialIcon name={hasChildren ? "account_tree" : "circle"} />
                  <span>{node.depth === 0 ? "全部资料" : node.label}</span>
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
        <CourseKnowledgeBuildCard
          courseId={courseId || ""}
          documentCount={documents.length}
          canBuild={canUpload}
          requestedAction={requestedAction}
          title={isRoot ? "课程知识库" : selectedNode?.label || "课程知识库"}
          toolbarEnd={<>
            {!loading && <span className="knowledge-library__count">{visibleDocuments.length} 份资料</span>}
            <label className="knowledge-library__search">
              <MaterialIcon name="search" />
              <input type="search" aria-label="搜索当前目录资料" placeholder="搜索资料标题" value={search} onChange={(event) => setSearch(event.target.value)} />
            </label>
            {canUpload && <>
              <input ref={fileRef} type="file" multiple hidden onChange={(event) => void upload(event.target.files)} />
              <button className="knowledge-library__upload" type="button" disabled={uploading || !selectedNode} onClick={() => fileRef.current?.click()}>
                <MaterialIcon name="upload_file" />{uploading ? "正在上传…" : "上传资料"}
              </button>
            </>}
          </>}
        />
        {error && <div className="knowledge-library__error">{error}</div>}
        <div className="knowledge-library__documents">
          {loading ? (
            <p className="knowledge-library__empty">正在读取资料…</p>
          ) : visibleDocuments.length === 0 ? (
            <p className="knowledge-library__empty">{search.trim() ? "没有找到匹配的资料" : "当前目录暂无资料"}</p>
          ) : visibleDocuments.map((document) => {
              const status = statusLabel(document.status);
              return (
                <article key={document.id} className="knowledge-library-document">
                  <button type="button" className="knowledge-library-document__preview" onClick={() => setPreviewDocument(document)}>
                    <span className="knowledge-library-document__icon"><MaterialIcon name={document.type === "web" ? "language" : "description"} /></span>
                    <span className="knowledge-library-document__copy">
                      <strong>{document.display_name || document.source_title || document.name}</strong>
                      <small>{document.type === "web" ? "网页" : "文档"} · {new Date(document.created_at).toLocaleDateString("zh-CN")}</small>
                    </span>
                  </button>
                  {status && <span className={`knowledge-library-document__status knowledge-library-document__status--${document.status}`}>{status}</span>}
                  <Dropdown
                    trigger={["click"]}
                    placement="bottomRight"
                    menu={{ items: [
                      { key: "details", label: "查看详情", icon: <MaterialIcon name="description" />, onClick: () => setPreviewDocument(document) },
                      ...(canUpload ? [
                        { key: "edit", label: "修改资料名称", icon: <MaterialIcon name="edit" />, onClick: () => { setEditingDocument(document); setEditName(document.display_name || document.source_title || document.name); setEditError(""); } },
                        { type: "divider" as const },
                        { key: "delete", label: "删除", danger: true, disabled: Boolean(deletingDocumentId), icon: <MaterialIcon name="delete" />, onClick: () => void deleteDocument(document) },
                      ] : []),
                    ] }}
                  >
                    <button type="button" className="knowledge-library-document__more" aria-label={`文档操作 ${document.display_name || document.source_title || document.name}`} aria-haspopup="menu" disabled={deletingDocumentId === document.id}>
                      <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.8" /><circle cx="12" cy="12" r="1.8" /><circle cx="19" cy="12" r="1.8" /></svg>
                    </button>
                  </Dropdown>
                </article>
              );
            })}
        </div>
      </div>
      <Modal title="修改资料名称" open={Boolean(editingDocument)} onCancel={() => !savingName && setEditingDocument(null)} onOk={() => void saveDocumentName()} confirmLoading={savingName} okText="保存" cancelText="取消" okButtonProps={{ disabled: !editName.trim() }} cancelButtonProps={{ disabled: savingName }} closable={!savingName} maskClosable={!savingName}>
        <label htmlFor="knowledge-document-name">资料名称</label>
        <Input id="knowledge-document-name" value={editName} maxLength={200} onChange={(event) => setEditName(event.target.value)} onPressEnter={() => void saveDocumentName()} disabled={savingName} />
        {editError && <p role="alert" className="knowledge-library__error">{editError}</p>}
      </Modal>
      {previewDocument && courseId && <KnowledgeDocumentPreviewDialog courseId={courseId} document={previewDocument} onClose={() => setPreviewDocument(null)} />}
    </section>
  );
}
