import { useEffect, useMemo, useRef, useState } from "react";
import {
  getKnowledgeBaseDocuments,
  getKnowledgeGraph,
  importKnowledgeGraphTextbook,
  saveKnowledgeGraph,
  uploadKnowledgeBaseDocument,
} from "../api/courses";
import type { KnowledgeBaseDocument, KnowledgeGraphNode, KnowledgeGraphTextbookImportResponse } from "../api/types";
import {
  AppSurface,
  GlassPanel,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  cx,
  routeHref,
  routes,
  useAppShell,
} from "../shared";

type FlatNode = {
  id: string;
  parentId: string | null;
  label: string;
  summary: string;
  level: number;
  type: string;
  hours: number | null;
};

type PositionedNode = FlatNode & {
  x: number;
  y: number;
  hasChildren: boolean;
};

type NodeResource = {
  title: string;
  type: string;
  meta: string;
};

const NODE_WIDTH = 250;
const NODE_HEIGHT = 56;
const H_GAP = 116;
const V_GAP = 30;
const PADDING_X = 56;
const PADDING_Y = 56;

function flattenGraph(root: KnowledgeGraphNode, parentId: string | null = null, level = 0): FlatNode[] {
  const current: FlatNode = {
    id: root.id,
    parentId,
    label: root.label,
    summary: root.data?.summary || "",
    level,
    type: root.data?.type || "concept",
    hours: null,
  };
  const children = Array.isArray(root.children) ? root.children.flatMap((child) => flattenGraph(child, root.id, level + 1)) : [];
  return [current, ...children];
}

function buildGraph(flatNodes: FlatNode[], rootId: string): KnowledgeGraphNode {
  const byParent = flatNodes.reduce<Record<string, FlatNode[]>>((acc, item) => {
    const key = item.parentId ?? "__root__";
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {});

  function makeNode(node: FlatNode): KnowledgeGraphNode {
    const children = (byParent[node.id] || []).map(makeNode);
    return {
      id: node.id,
      label: node.label,
      data: {
        level: node.level,
        summary: node.summary,
        hasChildren: children.length > 0,
        type: node.type,
      },
      children,
    };
  }

  const root = flatNodes.find((item) => item.id === rootId) || flatNodes[0];
  return makeNode(root);
}

function getChildrenMap(nodes: FlatNode[]) {
  return nodes.reduce<Record<string, FlatNode[]>>((acc, item) => {
    const key = item.parentId ?? "__root__";
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {});
}

function collectDescendants(nodeId: string, childrenMap: Record<string, FlatNode[]>) {
  const ids = new Set<string>();
  const queue = [nodeId];

  while (queue.length) {
    const current = queue.shift()!;
    const children = childrenMap[current] || [];
    for (const child of children) {
      if (!ids.has(child.id)) {
        ids.add(child.id);
        queue.push(child.id);
      }
    }
  }

  return ids;
}

function buildTreeLayout(root: FlatNode | null, childrenMap: Record<string, FlatNode[]>, expandedIds: Set<string>) {
  const positioned = new Map<string, PositionedNode>();
  const edges: Array<{ from: string; to: string }> = [];
  let leafCursor = 0;
  let maxDepth = 0;

  function visit(node: FlatNode, depth: number) {
    maxDepth = Math.max(maxDepth, depth);
    const children = childrenMap[node.id] || [];
    const visibleChildren = expandedIds.has(node.id) ? children : [];

    let centerY = 0;
    if (visibleChildren.length === 0) {
      centerY = PADDING_Y + leafCursor * (NODE_HEIGHT + V_GAP);
      leafCursor += 1;
    } else {
      const childYs = visibleChildren.map((child) => {
        edges.push({ from: node.id, to: child.id });
        return visit(child, depth + 1);
      });
      centerY = (childYs[0] + childYs[childYs.length - 1]) / 2;
    }

    positioned.set(node.id, {
      ...node,
      x: PADDING_X + depth * (NODE_WIDTH + H_GAP),
      y: centerY,
      hasChildren: children.length > 0,
    });

    return centerY;
  }

  if (root) visit(root, 0);

  const height = Math.max(720, PADDING_Y * 2 + Math.max(leafCursor - 1, 0) * (NODE_HEIGHT + V_GAP) + NODE_HEIGHT);
  const width = Math.max(1280, PADDING_X * 2 + (maxDepth + 1) * NODE_WIDTH + maxDepth * H_GAP);

  return { positioned, edges, width, height };
}

function createNode(parentId: string | null, siblingCount: number, parentLevel = 0): FlatNode {
  const suffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
  return {
    id: `node-${suffix}`,
    parentId,
    label: parentId ? `新节点 ${siblingCount + 1}` : "新主题",
    summary: "请补充当前节点说明",
    level: parentId ? parentLevel + 1 : 0,
    type: parentId ? "topic" : "chapter",
    hours: null,
  };
}

function generateHours(totalHours: number, nodes: FlatNode[]) {
  if (!nodes.length) return nodes;
  const totalWeight = nodes.reduce((sum, node) => sum + (node.parentId ? 1 : 1.4), 0);
  let allocated = 0;

  return nodes.map((node, index) => {
    const raw = Math.max(1, Math.round((totalHours * (node.parentId ? 1 : 1.4)) / totalWeight));
    const remaining = totalHours - allocated;
    const hours = index === nodes.length - 1 ? Math.max(1, remaining) : raw;
    allocated += hours;
    return { ...node, hours };
  });
}

function typeStyle(type: string) {
  switch (type) {
    case "chapter":
      return "bg-[#dbeafe] text-[#1d4ed8]";
    case "section":
      return "bg-[#dcfce7] text-[#166534]";
    case "topic":
      return "bg-[#fef3c7] text-[#b45309]";
    default:
      return "bg-[var(--accent-soft)] text-[var(--accent)]";
  }
}

function getNodeResources(node: FlatNode | null): NodeResource[] {
  if (!node) return [];
  const base = node.label.trim() || "当前节点";
  return [
    { title: `${base} 讲义`, type: "讲义", meta: "1 份" },
    { title: `${base} 练习`, type: "练习", meta: "8 题" },
    { title: `${base} 参考资料`, type: "资料", meta: "可查阅" },
  ];
}

function formatDocumentMeta(document: KnowledgeBaseDocument) {
  const typeLabel = document.type === "web" ? "网页资料" : "文件资料";
  const dateLabel = document.created_at ? new Date(document.created_at).toLocaleDateString("zh-CN") : "刚刚上传";
  return `${typeLabel} · ${dateLabel}`;
}

export function KnowledgeGraphPage() {
  const { selectedCourse, theme } = useAppShell();
  const course = selectedCourse;
  const isDark = theme === "dark";
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const graphViewportRef = useRef<HTMLDivElement | null>(null);
  const didHydrateRef = useRef(false);
  const saveTimerRef = useRef<number | null>(null);
  const lastSavedSignatureRef = useRef("");
  const dragStateRef = useRef<{ startX: number; startY: number; left: number; top: number } | null>(null);
  const knowledgeBaseUploadInputRef = useRef<HTMLInputElement | null>(null);

  const [uploadedMaterial, setUploadedMaterial] = useState("高等量子力学教材（第 4 章）.pdf");
  const [totalHours, setTotalHours] = useState("32");
  const [nodes, setNodes] = useState<FlatNode[]>([]);
  const [activeNodeId, setActiveNodeId] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [savingState, setSavingState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [panMode, setPanMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importSummary, setImportSummary] = useState<KnowledgeGraphTextbookImportResponse | null>(null);
  const [nodeDocuments, setNodeDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [uploadingKnowledgeBase, setUploadingKnowledgeBase] = useState(false);
  const [knowledgeBaseFeedback, setKnowledgeBaseFeedback] = useState<string | null>(null);
  const [knowledgeBaseFeedbackTone, setKnowledgeBaseFeedbackTone] = useState<"success" | "error" | null>(null);

  function applyGraphToCanvas(graph: KnowledgeGraphNode) {
    const flat = flattenGraph(graph);
    setNodes(flat);
    const root = flat.find((node) => node.parentId === null) ?? flat[0];
    setActiveNodeId(root?.id || "");
    setExpandedIds(root ? new Set([root.id]) : new Set());
  }

  useEffect(() => {
    if (!course?.id) return;
    const courseId = course.id;
    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        setError(null);
        const data = await getKnowledgeGraph(courseId);
        if (!cancelled) {
          applyGraphToCanvas(data.root);
          lastSavedSignatureRef.current = JSON.stringify(data.root);
          didHydrateRef.current = true;
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "知识图谱加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [course?.id]);

  const rootNode = nodes.find((node) => node.parentId === null) ?? nodes[0] ?? null;
  const activeNode = nodes.find((node) => node.id === activeNodeId) ?? rootNode ?? null;
  const childrenMap = useMemo(() => getChildrenMap(nodes), [nodes]);
  const layout = useMemo(() => buildTreeLayout(rootNode, childrenMap, expandedIds), [rootNode, childrenMap, expandedIds]);
  const isCourseRootSelected = activeNode?.parentId === null;
  const activeNodeResources = useMemo(
    () =>
      nodeDocuments.length
        ? nodeDocuments.map((document) => ({
            title: document.name,
            type: document.type === "web" ? "网页资料" : "文件资料",
            meta: formatDocumentMeta(document),
          }))
        : getNodeResources(activeNode),
    [activeNode, nodeDocuments],
  );

  async function loadNodeDocuments(node: FlatNode | null) {
    if (!course?.id || !node) {
      setNodeDocuments([]);
      return;
    }

    try {
      const documents = await getKnowledgeBaseDocuments(course.id, {
        scopeType: node.parentId === null ? "course" : "knowledge_point",
        scopeId: node.parentId === null ? undefined : node.id,
        aggregate: false,
        libraryType: "course",
      });
      setNodeDocuments(documents);
    } catch {
      setNodeDocuments([]);
    }
  }

  useEffect(() => {
    void loadNodeDocuments(activeNode);
  }, [course?.id, activeNodeId]);

  useEffect(() => {
    setKnowledgeBaseFeedback(null);
    setKnowledgeBaseFeedbackTone(null);
  }, [activeNodeId]);

  useEffect(() => {
    if (!course?.id || !rootNode || loading || importing || !didHydrateRef.current) return;

    const nextSignature = JSON.stringify(buildGraph(nodes, rootNode.id));
    if (nextSignature === lastSavedSignatureRef.current) return;

    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }

    setSavingState("saving");
    saveTimerRef.current = window.setTimeout(async () => {
      try {
        await saveKnowledgeGraph(course.id, { root: buildGraph(nodes, rootNode.id) });
        lastSavedSignatureRef.current = nextSignature;
        setSavingState("saved");
      } catch (err) {
        setSavingState("error");
        setError(err instanceof Error ? err.message : "自动保存失败");
      }
    }, 900);

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, [course?.id, importing, loading, nodes, rootNode]);

  function updateNode(nodeId: string, patch: Partial<FlatNode>) {
    setNodes((current) => current.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)));
  }

  function addChildNode(parentId: string | null) {
    const parent = parentId ? nodes.find((node) => node.id === parentId) ?? null : null;
    const siblingCount = nodes.filter((node) => node.parentId === parentId).length;
    const nextNode = createNode(parentId, siblingCount, parent?.level ?? 0);

    setNodes((current) => [...current, nextNode]);
    setActiveNodeId(nextNode.id);
    if (parentId) {
      setExpandedIds((current) => new Set(current).add(parentId));
    }
  }

  function removeNode(nodeId: string) {
    const target = nodes.find((node) => node.id === nodeId);
    if (!target?.parentId) return;

    const descendants = collectDescendants(nodeId, childrenMap);
    descendants.add(nodeId);

    setNodes((current) => current.filter((node) => !descendants.has(node.id)));
    setActiveNodeId(target.parentId);
  }

  function toggleNode(nodeId: string) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) {
        const descendants = collectDescendants(nodeId, childrenMap);
        next.delete(nodeId);
        for (const id of descendants) next.delete(id);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }

  async function handleTextbookSelection(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!course?.id || !file) return;

    try {
      setImporting(true);
      setError(null);
      const result = await importKnowledgeGraphTextbook(course.id, file);
      setUploadedMaterial(result.source_document.name);
      setImportSummary(result);
      applyGraphToCanvas(result.knowledge_graph.root);
      lastSavedSignatureRef.current = JSON.stringify(result.knowledge_graph.root);
      setSavingState("saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "教材导入失败");
    } finally {
      setImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleKnowledgeBaseUpload(fileList: FileList | null) {
    if (!course?.id || !activeNode || !fileList?.length) return;

    const files = Array.from(fileList);
    const targetNode = activeNode;
    const targetIsCourseRoot = targetNode.parentId === null;

    try {
      setUploadingKnowledgeBase(true);
      setKnowledgeBaseFeedback(null);
      setKnowledgeBaseFeedbackTone(null);

      for (const file of files) {
        await uploadKnowledgeBaseDocument(course.id, file, {
          scopeType: targetIsCourseRoot ? "course" : "knowledge_point",
          scopeId: targetIsCourseRoot ? undefined : targetNode.id,
          libraryType: "course",
        });
      }

      await loadNodeDocuments(targetNode);
      setKnowledgeBaseFeedback(`已导入到【${targetNode.label}】${targetIsCourseRoot ? "课程知识库" : "知识点知识库"}`);
      setKnowledgeBaseFeedbackTone("success");
    } catch (err) {
      setKnowledgeBaseFeedback(err instanceof Error ? err.message : "导入知识点知识库失败");
      setKnowledgeBaseFeedbackTone("error");
    } finally {
      setUploadingKnowledgeBase(false);
      if (knowledgeBaseUploadInputRef.current) {
        knowledgeBaseUploadInputRef.current.value = "";
      }
    }
  }

  function handlePanStart(event: React.MouseEvent<HTMLDivElement>) {
    if (!panMode || !graphViewportRef.current) return;
    dragStateRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      left: graphViewportRef.current.scrollLeft,
      top: graphViewportRef.current.scrollTop,
    };
  }

  function handlePanMove(event: React.MouseEvent<HTMLDivElement>) {
    if (!panMode || !graphViewportRef.current || !dragStateRef.current) return;
    const dx = event.clientX - dragStateRef.current.startX;
    const dy = event.clientY - dragStateRef.current.startY;
    graphViewportRef.current.scrollLeft = dragStateRef.current.left - dx;
    graphViewportRef.current.scrollTop = dragStateRef.current.top - dy;
  }

  function stopPan() {
    dragStateRef.current = null;
  }

  return (
    <AppSurface className="flex min-h-screen overflow-hidden">
      <SidebarDock
        className={cx(
          "h-screen gap-6 overflow-y-auto p-4",
          isDark ? "bg-[linear-gradient(180deg,#08111f_0%,#0f172a_100%)]" : "bg-[linear-gradient(180deg,#fcfdff_0%,#f2f6ff_100%)]",
        )}
      >
        <div className="px-2 py-4">
          <SidebarBackLink />
          <h2 className="text-xl font-extrabold tracking-tight text-[var(--accent-strong)]">知识图谱</h2>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--muted-text)]">{course?.title ?? "课程知识图谱"}</p>
        </div>
        <SidebarNav activeRoute={routes.graph} />
      </SidebarDock>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-40 flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl">
          <div>
            <h1 className="text-xl font-bold text-[var(--accent-strong)]">{course?.title ?? "课程"} 知识图谱</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setPanMode((current) => !current)}
              className={cx(
                "inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition",
                panMode
                  ? "border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent-strong)]"
                  : "border-[var(--shell-border)] bg-white text-[var(--muted-text)]",
              )}
            >
              <MaterialIcon name="pan_tool_alt" className="text-base" />
              手型拖动
            </button>
            <div className="rounded-full border border-[var(--shell-border)] bg-white px-4 py-2.5 text-sm font-semibold text-[var(--muted-text)]">
              {savingState === "saving" ? "自动保存中..." : savingState === "error" ? "自动保存失败" : "已自动保存"}
            </div>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 gap-6 p-6 lg:grid-cols-[280px_minmax(0,1fr)_320px] xl:grid-cols-[300px_minmax(0,1.2fr)_340px]">
          <GlassPanel className="h-[calc(100vh-116px)] overflow-y-auto border border-[var(--shell-border)] p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent-strong)]">图谱设置</p>
                <h3 className="mt-2 text-2xl font-black text-[var(--accent-strong)]">教材与学时</h3>
              </div>
              <MaterialIcon name="upload_file" className="text-[var(--accent)]" />
            </div>

            <div className="mt-5 space-y-4">
              <div className="space-y-4">
                <p className="text-sm font-semibold text-[var(--app-text)]">教材上传</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.md,.markdown,.txt"
                  className="hidden"
                  onChange={(event) => {
                    void handleTextbookSelection(event.target.files);
                  }}
                />
                <div className="mt-4 rounded-[18px] border border-[var(--shell-border)] bg-white/80 p-4 text-xs leading-6 text-[var(--muted-text)]">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={importing}
                    className="w-full rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {importing ? "导入教材中..." : "上传教材并解析"}
                  </button>
                  {importSummary ? (
                    <div className="mt-3 space-y-1">
                      <div>Parser: {importSummary.parser_used}</div>
                      <div>Outline: {importSummary.outline_source}</div>
                      <div>Splits: {importSummary.split_documents.length}</div>
                      <div>Indexed files: {importSummary.vectorized_documents.length}</div>
                    </div>
                  ) : (
                    <div className="mt-3"></div>
                  )}
                </div>
              </div>

              <div className="rounded-[24px] border border-[var(--shell-border)] bg-[var(--surface-subtle)] p-5">
                <label className="block text-sm font-semibold text-[var(--app-text)]">课程总学时</label>
                <div className="mt-3 flex items-center gap-2">
                  <input
                    value={totalHours}
                    onChange={(event) => setTotalHours(event.target.value)}
                    className="min-w-0 flex-1 rounded-2xl border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm text-[var(--app-text)] outline-none"
                    placeholder="输入总学时"
                  />
                  <span className="rounded-full bg-[var(--surface-elevated)] px-3 py-2 text-xs font-semibold text-[var(--muted-text)]">学时</span>
                </div>
                <button
                  type="button"
                  onClick={() => setNodes((current) => generateHours(Number(totalHours) || 32, current))}
                  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white"
                >
                  <MaterialIcon name="auto_graph" className="text-base" />
                  生成节点学时
                </button>
              </div>
            </div>
          </GlassPanel>

          <section className="flex min-h-0 flex-col overflow-hidden rounded-[32px] border border-[var(--shell-border)] bg-[var(--panel-surface)]">
            <div className="flex items-center justify-between border-b border-[var(--shell-border)] px-6 py-5">
              <div>
                <h3 className="text-2xl font-black text-[var(--accent-strong)]">知识图谱画布</h3>
              </div>
            </div>

            <div
              ref={graphViewportRef}
              onMouseDown={handlePanStart}
              onMouseMove={handlePanMove}
              onMouseUp={stopPan}
              onMouseLeave={stopPan}
              className={cx(
                "min-h-0 flex-1 overflow-auto bg-[radial-gradient(var(--graph-grid)_0.7px,transparent_0.7px)] [background-size:28px_28px]",
                panMode ? "cursor-grab active:cursor-grabbing" : "",
              )}
            >
              {loading ? (
                <div className="p-6 text-sm text-[var(--muted-text)]">正在加载知识图谱...</div>
              ) : error ? (
                <div className="p-6 text-sm text-rose-600">{error}</div>
              ) : (
                <div className="relative" style={{ width: layout.width, height: layout.height }}>
                  <svg className="pointer-events-none absolute inset-0" width={layout.width} height={layout.height}>
                    <defs>
                      <linearGradient id="graph-link" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.74" />
                      </linearGradient>
                    </defs>
                    {layout.edges.map((edge) => {
                      const from = layout.positioned.get(edge.from);
                      const to = layout.positioned.get(edge.to);
                      if (!from || !to) return null;

                      const startX = from.x + NODE_WIDTH;
                      const startY = from.y + NODE_HEIGHT / 2;
                      const endX = to.x;
                      const endY = to.y + NODE_HEIGHT / 2;
                      const curve = Math.max(48, (endX - startX) * 0.45);

                      return (
                        <path
                          key={`${edge.from}-${edge.to}`}
                          d={`M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`}
                          fill="none"
                          stroke="url(#graph-link)"
                          strokeWidth={activeNodeId === edge.to || activeNodeId === edge.from ? 3 : 2}
                          strokeLinecap="round"
                        />
                      );
                    })}
                  </svg>

                  {Array.from(layout.positioned.values()).map((node) => {
                    const expanded = expandedIds.has(node.id);
                    const active = node.id === activeNodeId;

                    return (
                      <div
                        key={node.id}
                        className={cx(
                          "absolute rounded-[18px] border bg-[var(--surface-elevated)] px-4 py-3 shadow-[0_16px_28px_var(--panel-shadow)] transition",
                          active ? "border-[var(--accent-border)] ring-2 ring-[var(--accent)]/20" : "border-[var(--shell-border)]",
                          panMode ? "pointer-events-none" : "",
                        )}
                        style={{ left: node.x, top: node.y, width: NODE_WIDTH, minHeight: NODE_HEIGHT }}
                      >
                        <button type="button" onClick={() => setActiveNodeId(node.id)} className="flex w-full items-center gap-3 text-left">
                          <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-2xl ${typeStyle(node.type)}`}>
                            <MaterialIcon name="hub" className="text-[15px]" />
                          </div>
                          <span className="min-w-0 flex-1 truncate text-sm font-bold text-[var(--app-text)]">
                            {node.label.replace(/<br\s*\/?>/gi, " / ")}
                          </span>
                          {node.hours ? (
                            <span className="shrink-0 rounded-full border border-[var(--accent-border)] bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-bold text-[var(--accent-strong)]">
                              {node.hours}h
                            </span>
                          ) : null}
                        </button>

                        {active ? (
                          <div className="mt-3 flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => addChildNode(node.id)}
                              className="grid h-8 w-8 place-items-center rounded-full bg-[var(--accent)] text-sm font-bold text-white"
                              aria-label="新增子节点"
                              title="新增子节点"
                            >
                              +
                            </button>
                            {node.parentId ? (
                              <button
                                type="button"
                                onClick={() => removeNode(node.id)}
                                className="grid h-8 w-8 place-items-center rounded-full border border-[#efc3c1] bg-white text-sm font-bold text-[#b42318]"
                                aria-label="删除节点"
                                title="删除节点"
                              >
                                x
                              </button>
                            ) : null}
                          </div>
                        ) : null}

                        {node.hasChildren ? (
                          <button
                            type="button"
                            onClick={() => toggleNode(node.id)}
                            className="absolute -right-3 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full border border-[var(--shell-border)] bg-white text-[var(--accent-strong)]"
                            aria-label={expanded ? "收起子节点" : "展开子节点"}
                            title={expanded ? "收起子节点" : "展开子节点"}
                          >
                            <span className={cx("text-sm transition-transform", expanded ? "rotate-90" : "rotate-0")}>{">"}</span>
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          <aside className="h-[calc(100vh-116px)]">
            <GlassPanel className="h-full overflow-y-auto border border-[var(--shell-border)] p-6">
              <div className="mb-6 flex items-start justify-between">
                <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--accent-strong)]">
                  当前节点
                </span>
              </div>
              {activeNode ? (
                <div className="space-y-4">
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">节点名称</label>
                    <input
                      value={activeNode.label}
                      onChange={(event) => updateNode(activeNode.id, { label: event.target.value })}
                      className="w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm font-semibold text-[var(--app-text)] outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">学时</label>
                    <div className="flex gap-3">
                      <input
                        value={activeNode.hours ?? ""}
                        onChange={(event) =>
                          updateNode(activeNode.id, {
                            hours: event.target.value === "" ? null : Math.max(0, Number(event.target.value) || 0),
                          })
                        }
                        className="flex-1 rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm font-semibold text-[var(--app-text)] outline-none"
                        inputMode="numeric"
                        placeholder="输入学时"
                      />
                      <div className="grid h-[52px] w-[52px] place-items-center rounded-[20px] bg-[var(--accent-soft)] text-[var(--accent)]">
                        <MaterialIcon name="schedule" />
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">节点说明</label>
                    <textarea
                      value={activeNode.summary}
                      onChange={(event) => updateNode(activeNode.id, { summary: event.target.value })}
                      className="min-h-[140px] w-full rounded-[20px] border border-[var(--shell-border)] bg-[var(--input-surface)] px-4 py-3 text-sm leading-7 text-[var(--app-text)] outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-text)]">当前节点资源</label>
                    <div className="mb-3">
                      <button
                        type="button"
                        onClick={() => knowledgeBaseUploadInputRef.current?.click()}
                        disabled={uploadingKnowledgeBase || !course?.id}
                        className="flex w-full items-center justify-center gap-2 rounded-[24px] bg-[var(--accent)] py-4 text-sm font-bold text-white shadow-[0_14px_32px_rgba(29,78,216,0.22)] transition hover:translate-y-[-1px] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
                      >
                        <MaterialIcon name="upload_file" className="text-base" />
                        {uploadingKnowledgeBase
                          ? "导入中..."
                          : isCourseRootSelected
                            ? "导入到课程总知识库"
                            : "按当前知识点导入"}
                      </button>
                      <span className="mt-2 block text-[11px] text-[var(--muted-text)]">
                        当前已有 {nodeDocuments.length} 份资料
                      </span>
                    </div>
                    <input
                      ref={knowledgeBaseUploadInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(event) => void handleKnowledgeBaseUpload(event.target.files)}
                    />
                    <div className="mb-3 text-[11px] text-[var(--muted-text)]">
                      {isCourseRootSelected ? "当前节点为课程根目录，文件会进入课程总知识库。" : "文件会带上当前知识点 ID，进入该知识点知识库。"}
                    </div>
                    {knowledgeBaseFeedback ? (
                      <div
                        className={cx(
                          "mb-3 rounded-[18px] px-3 py-2 text-xs font-semibold",
                          knowledgeBaseFeedbackTone === "error"
                            ? "bg-rose-50 text-rose-600"
                            : "bg-emerald-50 text-emerald-600",
                        )}
                      >
                        {knowledgeBaseFeedback}
                      </div>
                    ) : null}
                    <div className="space-y-3">
                      {activeNodeResources.map((resource) => (
                        <div key={resource.title} className="flex items-center gap-3 rounded-[18px] bg-[var(--surface-subtle)] p-3">
                          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-[var(--surface-elevated)] text-[var(--accent)]">
                            <MaterialIcon name="description" className="text-[16px]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-bold text-[var(--app-text)]">{resource.title}</div>
                            <div className="text-[11px] text-[var(--muted-text)]">
                              {resource.type} · {resource.meta}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <a
                    href={`${routeHref(routes.ai)}?node=${encodeURIComponent(activeNode.label.trim() || "当前节点")}`}
                    className="flex w-full items-center justify-center gap-2 rounded-[24px] bg-[var(--accent)] py-4 text-sm font-bold text-white"
                  >
                    和 AI 聊一聊
                    <MaterialIcon name="arrow_forward" className="text-sm" />
                  </a>
                </div>
              ) : (
                <div className="text-sm text-[var(--muted-text)]">请先选择一个图谱节点。</div>
              )}
            </GlassPanel>
          </aside>
        </div>
      </main>
    </AppSurface>
  );
}
