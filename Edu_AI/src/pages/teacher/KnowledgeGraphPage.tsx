import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Typography, Divider, Button, Tag, Space, Spin, message, Card, Tooltip, Input } from 'antd';
import { ReloadOutlined, SaveOutlined, InfoCircleOutlined, NodeIndexOutlined, ExpandOutlined, CompressOutlined, MessageOutlined, FileTextOutlined, ExclamationCircleOutlined, UploadOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import './KnowledgeGraphPage.css';
import { getInitialTreeGraphData, getNodeDetails, type TreeGraphNode, convertBackendToTreeGraph } from '../../services/teacher/knowledgeGraph';
import {
  getKnowledgeGraph as fetchKnowledgeGraph,
  importTextbookKnowledgeGraph,
  saveKnowledgeGraph,
  sendChatMessage,
  type KnowledgeGraphData,
  type TextbookKnowledgeGraphImportResponse,
} from '../../services/teacher/api';
import { getKnowledgeBaseDocuments, uploadKnowledgeBaseDocument, type KnowledgeBaseDocument } from '../../services/knowledgeBase';
import { writeWorkspaceScopeToSearch } from '../../services/teacher/workspaceScope';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../../context/AuthContext';

const { Title, Text, Paragraph } = Typography;

type G6Graph = {
  render?: () => void;
  destroy?: () => void;
  on?: (evt: string, handler: (e: any) => void) => void;
  setItemState?: (id: string, state: string, enabled: boolean) => void;
  resize?: (w: number, h: number) => void;
  fitView?: (padding?: number) => void;
  data?: (d: any) => void;
  read?: (d: any) => void;
  setData?: (d: any) => void;
  getData?: () => any;
  zoomTo?: (zoom: number, options?: any) => void;
  translateTo?: (x: number, y: number, options?: any) => void;
  translate?: (x: number, y: number, options?: any) => void;
  setTransform?: (transform: number[], options?: any) => void;
  getZoom?: () => number;
  getTranslate?: () => { x: number; y: number };
  focusElement?: (id: string, options?: any) => void;
  camera?: {
    setZoom?: (zoom: number, options?: any) => void;
    setPosition?: (pos: [number, number], options?: any) => void;
  };
  setViewport?: (viewport: [number, number, number]) => void;
  viewport?: { x: number; y: number; zoom: number };
};

function collectSubtreeIds(root: TreeGraphNode): Set<string> {
  const ids = new Set<string>();
  const stack: TreeGraphNode[] = [root];
  while (stack.length) {
    const n = stack.pop()!;
    ids.add(String(n.id));
    const children = Array.isArray(n.children) ? n.children : [];
    for (const c of children) stack.push(c);
  }
  return ids;
}

// 根据层级获取节点颜色
function getNodeColorByDepth(depth: number, hasChildren: boolean) {
  const colors = [
    { fill: '#e6f7ff', stroke: '#1890ff', text: '#0050b3' }, // Level 0 - 蓝色
    { fill: '#f6ffed', stroke: '#52c41a', text: '#389e0d' }, // Level 1 - 绿色
    { fill: '#fff7e6', stroke: '#fa8c16', text: '#d46b08' }, // Level 2 - 橙色
    { fill: '#fff1f0', stroke: '#ff4d4f', text: '#cf1322' }, // Level 3 - 红色
    { fill: '#f9f0ff', stroke: '#722ed1', text: '#531dab' }, // Level 4+ - 紫色
  ];
  const colorIndex = Math.min(depth, colors.length - 1);
  const baseColor = colors[colorIndex];
  if (!hasChildren) {
    return {
      fill: baseColor.fill + '80',
      stroke: baseColor.stroke,
      text: baseColor.text,
    };
  }
  return baseColor;
}

// 计算节点大小
function calculateNodeSize(label: string): [number, number] {
  const lines = label.split(/<br\s*\/?>/i);
  const lineCount = lines.length;
  let maxLineWidth = 0;
  lines.forEach(line => {
    const cleanLine = line.replace(/<[^>]*>/g, '');
    const chineseChars = (cleanLine.match(/[\u4e00-\u9fa5]/g) || []).length;
    const englishChars = cleanLine.length - chineseChars;
    const lineWidth = chineseChars * 20 + englishChars * 11;
    maxLineWidth = Math.max(maxLineWidth, lineWidth);
  });
  const width = Math.min(Math.max(maxLineWidth + 56, 260), 500);
  const height = Math.max(lineCount * 24 + 40, 64);
  return [width, height];
}

function treeToPositionGraph(root: TreeGraphNode) {
  const nodes: any[] = [];
  const edges: any[] = [];

  const countLeafNodes = (node: TreeGraphNode): number => {
    const children = Array.isArray(node.children) ? node.children : [];
    if (!children.length) return 1;
    return children.reduce((sum, child) => sum + countLeafNodes(child), 0);
  };

  // 根因修复：布局间距需要根据可见叶子节点数动态调整。
  // 否则在“根节点 + 多个一级子节点”时，fitView 会为了适配高度把整图缩得非常小。
  const leafCount = Math.max(1, countLeafNodes(root));
  const spacingX = 520;
  const spacingY = Math.max(42, Math.min(96, Math.floor(760 / Math.max(leafCount - 1, 1))));
  let cursorY = 0;

  const dfs = (node: TreeGraphNode, depth: number) => {
    const children = Array.isArray(node.children) ? node.children : [];
    const [w, h] = calculateNodeSize(node.label);

    const nodeModel = {
      id: String(node.id),
      data: {
        label: node.label,
        depth,
        ...node.data,
        hasChildren: children.length > 0,
      },
      style: {
        x: depth * spacingX,
        y: 0, // 稍后赋值
        // 务必保留宽高，自定义边计算需要用到
        width: w,
        height: h,
      },
      // 兼容性字段
      size: [w, h],
      width: w,
      height: h,
      type: 'rect',
    };
    
    if (!children.length) {
      const y = cursorY;
      cursorY += spacingY;

      nodes.push({
        ...nodeModel,
        style: { ...nodeModel.style, y },
        y, // 兼容 v4
        x: depth * spacingX, // 兼容 v4
      });
      return y;
    }

    let firstY = Infinity;
    let lastY = -Infinity;
    
    for (const child of children) {
      const cy = dfs(child, depth + 1);
      firstY = Math.min(firstY, cy);
      lastY = Math.max(lastY, cy);
      
      const edge = { 
        source: String(node.id), 
        target: String(child.id),
        // 这里不需要指定 ports 或 anchors，由自定义边处理
      };
      edges.push(edge);
    }
    
    const y = (firstY + lastY) / 2;
    
    nodes.push({
      ...nodeModel,
      style: { ...nodeModel.style, y },
      y,
      x: depth * spacingX,
    });
    return y;
  };

  dfs(root, 0);
  return { nodes, edges };
}

function findNodeInTree(root: TreeGraphNode, nodeId: string): TreeGraphNode | null {
  if (String(root.id) === String(nodeId)) return root;
  if (!root.children) return null;
  for (const child of root.children) {
    const hit = findNodeInTree(child, nodeId);
    if (hit) return hit;
  }
  return null;
}

function buildCollapsedTree(full: TreeGraphNode, depth: number): TreeGraphNode {
  const clone: TreeGraphNode = {
    id: full.id,
    label: full.label,
    data: {
      ...full.data,
      hasChildren: full.data?.hasChildren ?? ((full.children?.length ?? 0) > 0),
    },
    children: [],
  };
  if (depth <= 0) return clone;
  const children = Array.isArray(full.children) ? full.children : [];
  clone.children = children.map((c) => buildCollapsedTree(c, depth - 1));
  return clone;
}

const KnowledgeGraphPage: React.FC = () => {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const graphWrapRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<G6Graph | null>(null);
  const fullTreeRef = useRef<TreeGraphNode | null>(null);
  const visibleTreeRef = useRef<TreeGraphNode | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const expandedNodeIdsRef = useRef<Set<string>>(new Set());
  const [dataSource, setDataSource] = useState<'backend' | 'fallback' | 'unknown'>('unknown');
  const [rootChildrenCount, setRootChildrenCount] = useState<number>(0);
  const [rootNodeId, setRootNodeId] = useState<string | null>(null);
  
  // Chat State
  const [chatMessages, setChatMessages] = useState<Array<{ user: 'You' | 'AI'; text: string; sources?: any[] }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [nodeDocuments, setNodeDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [nodeDocumentIds, setNodeDocumentIds] = useState<string[]>([]);
  const [uploadingKnowledgeBase, setUploadingKnowledgeBase] = useState(false);
  const [importingTextbookKnowledgeGraph, setImportingTextbookKnowledgeGraph] = useState(false);
  const [textbookImportSummary, setTextbookImportSummary] = useState<TextbookKnowledgeGraphImportResponse | null>(null);
  const clickTimerRef = useRef<number | null>(null);
  const knowledgeBaseUploadInputRef = useRef<HTMLInputElement | null>(null);
  const textbookImportInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    expandedNodeIdsRef.current = expandedNodeIds;
  }, [expandedNodeIds]);

  const fetchNodeDocuments = React.useCallback(async (nodeId: string) => {
    if (!courseId || !fullTreeRef.current || !token) {
      setNodeDocuments([]);
      setNodeDocumentIds([]);
      return;
    }
    try {
      const isCourseRootNode = String(fullTreeRef.current.id) === String(nodeId);
      try {
        const relatedDocs = await getKnowledgeBaseDocuments(courseId, token, {
          scopeType: isCourseRootNode ? 'course' : 'knowledge_point',
          scopeId: isCourseRootNode ? undefined : nodeId,
          aggregate: false,
          libraryType: 'course',
        });
        setNodeDocuments(relatedDocs);
        setNodeDocumentIds(relatedDocs.map(doc => doc.id));
      } catch (error) {
        setNodeDocuments([]);
        setNodeDocumentIds([]);
      }
    } catch {
      setNodeDocuments([]);
      setNodeDocumentIds([]);
    }
  }, [courseId, token]);

  useEffect(() => {
    if (selectedNodeId && courseId) {
      const timer = setTimeout(() => {
        fetchNodeDocuments(selectedNodeId).catch(() => {});
      }, 0);
      return () => clearTimeout(timer);
    } else {
      setNodeDocuments([]);
      setNodeDocumentIds([]);
    }
  }, [selectedNodeId, courseId, fetchNodeDocuments]);

  const handleSendChatMessage = async () => {
    if (!chatInput.trim() || chatLoading || !selectedNodeId) return;
    const userMessage = { user: 'You' as const, text: chatInput };
    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setChatLoading(true);
    try {
      const response = await sendChatMessage(userMessage.text, nodeDocumentIds);
      const aiMessage = { user: 'AI' as const, text: response.text, sources: response.sources || [] };
      setChatMessages(prev => [...prev, aiMessage]);
    } catch {
      setChatMessages(prev => [...prev, { user: 'AI', text: '抱歉，发送消息时出错，请稍后再试。' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleJumpToAiStudio = () => {
    if (!courseId || !selectedNodeId || !fullTreeRef.current) {
      return;
    }
    const node = findNodeInTree(fullTreeRef.current, selectedNodeId);
    const nextSearch = writeWorkspaceScopeToSearch(
      new URLSearchParams(),
      {
        scopeType: isCourseRootSelected ? 'course' : 'knowledge_point',
        scopeId: isCourseRootSelected ? undefined : selectedNodeId,
        scopeLabel: isCourseRootSelected ? undefined : (node?.label || selectedNodeId),
      },
    );
    navigate(`/course/${courseId}/studio?${nextSearch.toString()}`);
  };

  const selectedDetails = useMemo(() => {
    if (!selectedNodeId) return null;
    return getNodeDetails(selectedNodeId, fullTreeRef.current ?? undefined);
  }, [selectedNodeId]);

  const isCourseRootSelected = useMemo(() => {
    if (!selectedNodeId || !rootNodeId) {
      return false;
    }
    return String(selectedNodeId) === String(rootNodeId);
  }, [selectedNodeId, rootNodeId]);

  const handleKnowledgeBaseUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';

    if (!files.length || !courseId || !selectedNodeId || !token || !selectedDetails) {
      return;
    }

    try {
      setUploadingKnowledgeBase(true);
      for (const file of files) {
        await uploadKnowledgeBaseDocument(courseId, file, token, undefined, {
          scopeType: isCourseRootSelected ? 'course' : 'knowledge_point',
          scopeId: isCourseRootSelected ? undefined : selectedNodeId,
          libraryType: 'course',
        });
      }
      await fetchNodeDocuments(selectedNodeId);
      message.success(`已导入到【${selectedDetails.label}】课程知识库`);
    } catch (error) {
      console.error('knowledge graph course knowledge upload failed:', error);
      message.error(error instanceof Error ? error.message : '导入知识点课程知识库失败');
    } finally {
      setUploadingKnowledgeBase(false);
    }
  };

  const openKnowledgeBaseUpload = () => {
    if (!selectedNodeId || uploadingKnowledgeBase) {
      return;
    }
    knowledgeBaseUploadInputRef.current?.click();
  };


  const syncGraphSize = React.useCallback((fitPadding = 8) => {
    const g = graphRef.current as any;
    const host = graphWrapRef.current;
    if (!g || !host) return;
    const rect = host.getBoundingClientRect();
    const w = Math.floor(rect.width);
    const h = Math.floor(rect.height);
    if (w > 0 && h > 0) {
      g.resize?.(w, h);
      try { g.fitView?.(fitPadding); } catch {}
    }
  }, []);

  const applyGraphRoot = async (root: TreeGraphNode) => {
    fullTreeRef.current = root;
    setRootNodeId(String(root.id));
    setRootChildrenCount(Array.isArray(root.children) ? root.children.length : 0);
    const collapsed = buildCollapsedTree(root, 1);
    visibleTreeRef.current = collapsed;
    setExpandedNodeIds(new Set());
    setSelectedNodeId(String(root.id));
    await setGraphDataAndRender(collapsed);
  };

  const setGraphDataAndRender = async (root: TreeGraphNode, options?: { focusNodeId?: string; focusSubtreeRootId?: string }) => {
    if (!containerRef.current) return;
    const graph = graphRef.current;
    if (!graph) return;
    
    const graphData = treeToPositionGraph(root);
    
    // 数据清洗，确保 ID 为字符串
    graphData.nodes.forEach((node: any) => {
      node.id = String(node.id);
      if (!node.style) node.style = {};
      // 确保 size 属性存在
      if (node.data?.label && !node.size) {
        const [w, h] = calculateNodeSize(node.data.label);
        node.size = [w, h];
        node.style.size = [w, h];
        node.style.width = w;
        node.style.height = h;
      }
      // 确保所有节点都有 anchorPoints (G6 v4 fallback / 某些渲染策略需要)
      if (!node.anchorPoints) {
        node.anchorPoints = [[1, 0.5], [0, 0.5]];
      }
    });

    // 构建节点几何信息，用于强制给边写入 sourcePoint/targetPoint（右中 -> 左中）
    const nodeGeom = new Map<string, { x: number; y: number; w: number; h: number }>();
    graphData.nodes.forEach((n: any) => {
      const id = String(n.id);
      // 优先使用顶层 x/y（G6 通常以 model.x/model.y 为坐标），否则退回 style.x/style.y
      const x = Number(n?.x ?? n?.style?.x ?? 0);
      const y = Number(n?.y ?? n?.style?.y ?? 0);
      const w = Number(n?.style?.width ?? n?.width ?? (Array.isArray(n?.style?.size) ? n.style.size[0] : (Array.isArray(n?.size) ? n.size[0] : 260)));
      const h = Number(n?.style?.height ?? n?.height ?? (Array.isArray(n?.style?.size) ? n.style.size[1] : (Array.isArray(n?.size) ? n.size[1] : 64)));
      nodeGeom.set(id, { x, y, w, h });
    });

    graphData.edges.forEach((edge: any) => {
      edge.source = String(edge.source);
      edge.target = String(edge.target);

      const s = nodeGeom.get(edge.source);
      const t = nodeGeom.get(edge.target);
      if (s && t) {
        // 这里按“x/y 是节点中心”优先；若是左上角，则再调一次
        let sp = { x: s.x + s.w / 2, y: s.y };
        let tp = { x: t.x - t.w / 2, y: t.y };
        // 如果明显偏差，尝试将 x/y 视为左上角
        if (Math.abs((sp.y - (s.y + s.h / 2))) > 1e-3) {
          sp = { x: s.x + s.w, y: s.y + s.h / 2 };
        }
        if (Math.abs((tp.y - (t.y + t.h / 2))) > 1e-3) {
          tp = { x: t.x, y: t.y + t.h / 2 };
        }
        // 尽可能覆盖 G6 v5 的不同字段命名
        (edge as any).sourcePoint = sp;
        (edge as any).targetPoint = tp;
        edge.style = { ...(edge.style || {}), sourcePoint: sp, targetPoint: tp };
      }
    });

    const finalGraphData = {
      nodes: Array.isArray(graphData.nodes) ? graphData.nodes : [],
      edges: Array.isArray(graphData.edges) ? graphData.edges : [],
    };
    
    const graphAny: any = graph as any;
    // 使用最稳妥的 read/data 方法
    if (graph.data) {
      graph.data(finalGraphData);
    } else if (graph.read) {
      graph.read(finalGraphData);
    } else if (typeof graphAny.setData === 'function') {
      graphAny.setData(finalGraphData);
    }

    graph.render?.();
    
    
    // --- 修改开始：更稳健的尺寸同步 + fitView 调用 ---
    // 先同步一次图容器尺寸，确保不是旧的 600x600 画布
    syncGraphSize(20);

    // 使用 requestAnimationFrame 确保渲染循环完成，增加延迟确保数据完全渲染
    requestAnimationFrame(() => {
      setTimeout(() => {
        try {
          // 再同步一次尺寸，避免右侧面板/布局动画导致的尺寸延迟
          syncGraphSize(20);

          if (options?.focusSubtreeRootId) {
            const subtreeRoot = findNodeInTree(root, options.focusSubtreeRootId);
            if (subtreeRoot) {
              const ids = collectSubtreeIds(subtreeRoot);
              const pts = (graphData.nodes as any[])
                .filter((n) => ids.has(String(n.id)))
                .map((n) => ({ x: Number(n?.style?.x ?? 0), y: Number(n?.style?.y ?? 0) }));

              if (pts.length) {
                if (typeof graphAny.focusElement === 'function') {
                  // 交给 G6 内部处理聚焦/缩放，避免手动 translate/zoom 引起视口异常
                  graphAny.focusElement(options.focusSubtreeRootId, { easing: 'easeCubic', duration: 300 });
                } else {
                  graph.fitView?.(8);
                }
                return;
              }
            }
          } else if (options?.focusNodeId && typeof graphAny.focusElement === 'function') {
            graphAny.focusElement(options.focusNodeId, { easing: 'easeCubic', duration: 300, zoom: 0.9 });
          } else {
            // 不手动算 viewport，直接适配视图（避免 NaN/undefined）
            graph.fitView?.(20);
          }
        } catch (e) {
          console.warn('FitView failed', e);
        }
      }, 300); // 增加到 300ms，确保数据完全渲染后再适配视图
    });
    // --- 修改结束 ---
  };

  const ensureGraphInstance = async () => {
    if (!containerRef.current || graphRef.current) return;

    const G6 = await import('@antv/g6');
    const G6Any = G6 as any;
    const GraphCtor = G6Any.Graph;

    const edgeTypeToUse = 'cubic-horizontal';

    // --- 透传 preset 布局：不改动数据中的 x/y ---
    try {
      class PresetLayout {
        async execute(model: any) {
          const nodes = Array.isArray(model?.nodes) ? model.nodes : [];
          const edges = Array.isArray(model?.edges) ? model.edges : [];
          return {
            nodes: nodes.map((node: any) => ({
              ...node,
              id: String(node?.id ?? ''),
              style: {
                ...(node?.style || {}),
                x: node?.style?.x ?? 0,
                y: node?.style?.y ?? 0,
              },
            })),
            edges: edges.map((edge: any) => ({ ...edge })),
          };
        }
      }
      if (G6Any.register) {
        try { G6Any.register('layout', 'preset', PresetLayout); } catch {}
      }
    } catch (e) {
      console.warn('Layout reg failed', e);
    }

    // 用外层容器（.graph-container）的真实尺寸来初始化/resize，避免内部 div 被算成 600x600
    const sizeHost = graphWrapRef.current ?? containerRef.current;
    const initialWidth = sizeHost.clientWidth || sizeHost.offsetWidth || 800;
    const initialHeight = sizeHost.clientHeight || sizeHost.offsetHeight || 600;

    const graph: G6Graph = new GraphCtor({
      container: containerRef.current,
      width: initialWidth,
      height: initialHeight,
      autoFit: false, // 禁用自动适应，避免与 ResizeObserver 的 resize 冲突
      padding: 0,
      layout: { type: 'preset' },
      defaultNode: {
        type: 'rect',
        anchorPoints: [[1, 0.5], [0, 0.5]],
        style: {
          radius: 6,
          stroke: '#1677ff',
          lineWidth: 2,
          fill: '#ffffff',
        },
      },
      node: {
        type: 'rect',
        style: (d: any) => {
          const label = d?.data?.label ?? '';
          let w: number, h: number;
          if (d?.style?.width && d?.style?.height) {
            w = d.style.width;
            h = d.style.height;
          } else {
            const size = calculateNodeSize(label);
            w = size[0];
            h = size[1];
          }
          const nodeColor = getNodeColorByDepth(d?.data?.depth ?? 0, d?.data?.hasChildren ?? false);
          return {
            fill: nodeColor.fill,
            stroke: nodeColor.stroke,
            lineWidth: 2,
            radius: 6,
            cursor: 'pointer',
            shadowBlur: 4,
            shadowColor: 'rgba(0, 0, 0, 0.1)',
            size: [w, h],
            width: w,
            height: h,
            labelText: label.replace(/<br\s*\/?>/gi, '\n'),
            labelFill: nodeColor.text,
            labelFontSize: 13,
            labelFontWeight: 500,
            labelPlacement: 'center',
            labelPadding: [10, 20],
          };
        },
        state: {
          hover: { lineWidth: 3, shadowBlur: 8, shadowColor: 'rgba(0, 0, 0, 0.15)' },
          selected: { lineWidth: 3, shadowBlur: 8, shadowColor: 'rgba(24, 144, 255, 0.3)' },
        },
      },
      edge: {
        type: edgeTypeToUse,
        style: {
          stroke: '#A3B1BF',
          strokeOpacity: 1,
          lineWidth: 2,
          endArrow: { path: 'M 0,0 L 8,4 L 8,-4 Z', fill: '#A3B1BF' },
        },
        state: { hover: { stroke: '#1890ff', lineWidth: 3 } },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'click-select'],
      plugins: [],
    });

    const pickNodeId = (evt: any) => String(
      evt?.data?.id ?? evt?.data?.data?.id ?? evt?.item?.get?.('id') ?? evt?.item?._cfg?.id ?? evt?.target?.id ?? evt?.target?._cfg?.id ?? ''
    );

    const handlePick = (evt: any) => {
      const nodeId = pickNodeId(evt);
      if (!nodeId) return;
      if (clickTimerRef.current) {
        window.clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      clickTimerRef.current = window.setTimeout(() => {
        setSelectedNodeId(nodeId);
        clickTimerRef.current = null;
      }, 220);
    };

    const handleDbl = (evt: any) => {
      const nodeId = pickNodeId(evt);
      if (!nodeId) return;
      if (clickTimerRef.current) {
        window.clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      setSelectedNodeId(nodeId);
      setTimeout(() => {
        toggleExpandById(nodeId).catch(() => {});
      }, 0);
    };

    graph.on?.('node:pointerenter', (evt: any) => {
      const nodeId = pickNodeId(evt);
      if (nodeId) graph.setItemState?.(nodeId, 'hover', true);
    });
    graph.on?.('node:pointerleave', (evt: any) => {
      const nodeId = pickNodeId(evt);
      if (nodeId) graph.setItemState?.(nodeId, 'hover', false);
    });
    graph.on?.('node:click', handlePick);
    graph.on?.('node:dblclick', handleDbl);
    graph.on?.('canvas:click', () => setSelectedNodeId(null));
    
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const g = graphRef.current;
      if (!g) return;

      const { width, height } = entry.contentRect;
      if (!(width > 0 && height > 0)) return;

      window.requestAnimationFrame(() => {
        g.resize?.(width, height);
        const anyG = g as any;
        if (anyG.__fitTimer) window.clearTimeout(anyG.__fitTimer);
        anyG.__fitTimer = window.setTimeout(() => {
          try { g.fitView?.(20); } catch {}
        }, 80);
      });
    });
    ro.observe(sizeHost);
    (graph as any).__ro = ro;

    graphRef.current = graph;

    // 初始化后：对齐一次尺寸与视图
    window.requestAnimationFrame(() => {
      const g = graphRef.current;
      const el = containerRef.current;
      if (!g || !el) return;
      const host = graphWrapRef.current ?? el;
      const w = host.clientWidth || host.offsetWidth;
      const h = host.clientHeight || host.offsetHeight;
      if (w > 0 && h > 0) {
        g.resize?.(w, h);
        try { g.fitView?.(20); } catch {}
      }
    });
  };

  const loadGraph = async () => {
    // 先把图容器尺寸同步到最新布局，防止首次渲染使用旧尺寸
    syncGraphSize(20);
    setInitError(null);
    setLoading(true);
    setSelectedNodeId(null);
    try {
      await ensureGraphInstance();
      let root: TreeGraphNode | null = null;
      if (courseId) {
        try {
          const backend = await fetchKnowledgeGraph(courseId);
          root = convertBackendToTreeGraph(backend.root);
          setDataSource('backend');
        } catch (e: any) {
          message.warning(`后端数据获取失败，使用示例数据`);
          setDataSource('fallback');
        }
      }
      if (!root) {
        root = getInitialTreeGraphData();
        setDataSource('fallback');
      }
      await applyGraphRoot(root);

      // 数据加载完成后再做一次尺寸同步与视图适配
      window.requestAnimationFrame(() => {
        syncGraphSize(20);
      });
    } catch (e: any) {
      setInitError(e?.message || String(e));
      setDataSource('unknown');
    } finally {
      setLoading(false);
    }
  };

  const openTextbookImport = () => {
    if (!courseId || importingTextbookKnowledgeGraph) {
      return;
    }
    textbookImportInputRef.current?.click();
  };

  const handleTextbookImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file || !courseId) {
      return;
    }

    try {
      setImportingTextbookKnowledgeGraph(true);
      setInitError(null);
      const result = await importTextbookKnowledgeGraph(courseId, file);
      const root = convertBackendToTreeGraph(result.knowledge_graph.root);
      setDataSource('backend');
      setTextbookImportSummary(result);
      await applyGraphRoot(root);
      if (result.warnings.length) {
        message.warning(`教材已导入，但有 ${result.warnings.length} 条提示信息`);
      } else {
        message.success(`已根据教材《${result.source_document.name}》生成课程知识图谱`);
      }
    } catch (error) {
      console.error('textbook knowledge graph import failed:', error);
      message.error(error instanceof Error ? error.message : '教材导入失败');
    } finally {
      setImportingTextbookKnowledgeGraph(false);
    }
  };

  const handleSave = async () => {
    if (!courseId || !fullTreeRef.current) return;
    try {
      setLoading(true);
      await saveKnowledgeGraph(courseId, { root: fullTreeRef.current as any });
      message.success('保存成功');
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const toggleExpandById = async (nodeId: string) => {
    const full = fullTreeRef.current;
    const visible = visibleTreeRef.current;
    if (!full || !visible) return;
    const fullNode = findNodeInTree(full, nodeId);
    const fullChildren = Array.isArray(fullNode?.children) ? fullNode!.children! : [];
    
    if (fullChildren.length === 0) {
      const g: any = graphRef.current as any;
      if (typeof g?.focusElement === 'function') g.focusElement(nodeId);
      return;
    }

    if (expandedNodeIdsRef.current.has(nodeId)) {
      const visibleNode = findNodeInTree(visible, nodeId);
      if (visibleNode) visibleNode.children = [];
      const nextExpanded = new Set(expandedNodeIdsRef.current);
      nextExpanded.delete(nodeId);
      expandedNodeIdsRef.current = nextExpanded;
      setExpandedNodeIds(nextExpanded);
      await setGraphDataAndRender(visible);
    } else {
      const visibleNode = findNodeInTree(visible, nodeId);
      if (visibleNode) visibleNode.children = fullChildren.map((c) => buildCollapsedTree(c, 0));
      const nextExpanded = new Set(expandedNodeIdsRef.current);
      nextExpanded.add(nodeId);
      expandedNodeIdsRef.current = nextExpanded;
      setExpandedNodeIds(nextExpanded);
      await setGraphDataAndRender(visible, { focusSubtreeRootId: nodeId });
    }
  };

  useEffect(() => {
    let disposed = false;
    (async () => {
      if (disposed) return;
      await loadGraph();
    })();
    return () => {
      disposed = true;
      if (clickTimerRef.current) window.clearTimeout(clickTimerRef.current);
      const g = graphRef.current as any;
      if (g?.__ro) g.__ro.disconnect();
      g?.destroy?.();
      graphRef.current = null;
    };
  }, [courseId]);

  return (
    <div className="knowledge-graph-page" style={{ height: '100%', width: '100%', padding: 0, margin: 0, minHeight: 0, position: 'relative' }}>
      <div
        ref={graphWrapRef}
        className="knowledge-graph-canvas-host"
        style={{ position: 'absolute', left: 0, top: 0, bottom: 0, right: 460, overflow: 'hidden', padding: 0, margin: 0, minHeight: 0 }}
      >
        <Spin spinning={loading} tip="加载知识图谱中..." style={{ position: 'absolute', inset: 0, zIndex: 10 }} />
        {/* 修改这个 div 的样式，强制绝对定位撑满 */}
        <div 
          ref={containerRef} 
          style={{ 
            position: 'absolute', // 关键：绝对定位
            top: 0, 
            left: 0, 
            right: 0,
            bottom: 0,
            width: '100%', 
            height: '100%',
            minWidth: '100%',
            minHeight: '100%'
          }} 
        />
      </div>
      <div className="details-sider" style={{ width: 460, borderLeft: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column', minHeight: 0, position: 'absolute', right: 0, top: 0, bottom: 0, zIndex: 20, pointerEvents: 'auto' }}>
        <Card style={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }} 
          title={
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, lineHeight: 1.2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <NodeIndexOutlined style={{ color: '#ffffff', fontSize: 16 }} />
                <span>{selectedDetails?.label || '课程介绍'}</span>
              </div>
              <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12 }}>
                {courseId ? `课程 ID：${courseId}` : '未指定课程'}
              </Text>
            </div>
          }
          extra={
            <Space size={8}>
              <Tooltip title="上传教材并重建课程知识图谱">
                <Button
                  size="small"
                  icon={<UploadOutlined />}
                  onClick={openTextbookImport}
                  loading={importingTextbookKnowledgeGraph}
                  disabled={!courseId}
                >
                  教材导入
                </Button>
              </Tooltip>
              <Tooltip title="重新加载">
                <Button size="small" icon={<ReloadOutlined />} onClick={loadGraph} loading={loading} />
              </Tooltip>
              <Tooltip title="保存">
                <Button size="small" type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={loading} />
              </Tooltip>
            </Space>
          }
          bordered={false}
          className="details-card"
          bodyStyle={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1, minHeight: 0, paddingBottom: 16 }}
        >
          <input
            ref={textbookImportInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md"
            style={{ display: 'none' }}
            onChange={handleTextbookImport}
          />
          {initError && (
            <div style={{ marginBottom: 12 }}>
              <Tag color="red" style={{ borderRadius: 999, padding: '4px 10px' }}>{initError}</Tag>
            </div>
          )}
          {textbookImportSummary && (
            <div
              style={{
                marginBottom: 12,
                border: '1px solid #d6e4ff',
                background: '#f5f9ff',
                borderRadius: 12,
                padding: 12,
              }}
            >
              <Space size={[8, 8]} wrap>
                <Tag color="blue">教材 {textbookImportSummary.source_document.name}</Tag>
                <Tag color="geekblue">切片 {textbookImportSummary.split_documents.length}</Tag>
                <Tag color="cyan">向量化 {textbookImportSummary.vectorized_documents.length}</Tag>
                {textbookImportSummary.parser_used ? <Tag>{textbookImportSummary.parser_used}</Tag> : null}
                {textbookImportSummary.outline_source ? <Tag>{textbookImportSummary.outline_source}</Tag> : null}
              </Space>
              {textbookImportSummary.warnings.length ? (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">提示：{textbookImportSummary.warnings.join('；')}</Text>
                </div>
              ) : null}
            </div>
          )}
          {!selectedDetails ? (
            <div style={{ padding: '24px 16px' }}>
              <div
                style={{
                  background: '#ffffff',
                  borderRadius: 12,
                  padding: 16,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      background: '#f0f5ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <InfoCircleOutlined style={{ fontSize: 20, color: '#1d39c4' }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <Text strong style={{ fontSize: 14, color: '#1f1f1f' }}>课程介绍</Text>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        点击左侧图谱中的任意节点，查看内容概览并发起智能问答
                      </Text>
                    </div>
                  </div>
                </div>

                <div style={{ background: '#fafafa', borderRadius: 10, padding: 12, marginBottom: 12 }}>
                  <Text style={{ fontSize: 12, color: '#595959', lineHeight: 1.6 }}>
                    交互提示：
                    <br />
                    1. 单击：查看节点详情
                    <br />
                    2. 双击：展开/收起子节点
                    <br />
                    3. 滚轮：缩放画布；拖拽：移动画布
                  </Text>
                </div>

                <Space size={8} wrap>
                  <Button
                    icon={<UploadOutlined />}
                    onClick={openTextbookImport}
                    loading={importingTextbookKnowledgeGraph}
                    disabled={!courseId}
                  >
                    导入教材生成图谱
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={loadGraph} loading={loading}>
                    重新加载
                  </Button>
                  <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={loading} disabled={!courseId}>
                    保存
                  </Button>
                </Space>

                {!courseId && (
                  <div style={{ marginTop: 12 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      当前未传入课程 ID，保存按钮已禁用
                    </Text>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
              <div style={{ marginBottom: 16, background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                  <div style={{ flex: 1 }}>
                    <Title level={4} style={{ color: '#1d39c4', margin: '0 0 12px 0', fontWeight: 600 }}>
                      {selectedDetails.label}
                    </Title>
                    <Space size={[8, 8]} wrap>
                      <Tag color="#d6e4ff" style={{ color: '#1d39c4', padding: '2px 8px', borderRadius: 12 }}>Level {selectedDetails.level}</Tag>
                      {selectedDetails.hasChildren ? (
                        <Tag color="#f6ffed" style={{ color: '#389e0d', padding: '2px 8px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ display: 'inline-block', width: 6, height: 6, background: '#52c41a', borderRadius: '50%' }} />
                          包含子节点
                        </Tag>
                      ) : (
                        <Tag style={{ color: '#8c8c8c', padding: '2px 8px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ display: 'inline-block', width: 6, height: 6, background: '#d9d9d9', borderRadius: '50%' }} />
                          叶子节点
                        </Tag>
                      )}
                </Space>
                  </div>
                  <div style={{ width: 80, height: 80, borderRadius: 8, background: '#f0f5ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <NodeIndexOutlined style={{ fontSize: 32, color: '#1d39c4', opacity: 0.6 }} />
                  </div>
                </div>

                <div style={{ 
                  background: '#fafafa', 
                  borderRadius: 8, 
                  padding: '12px 16px',
                  marginBottom: 16,
                  borderLeft: '3px solid #1d39c4'
                }}>
                  <Text style={{ color: '#595959', lineHeight: 1.6 }}>
                    {selectedDetails.summary || '暂无课程内容简介，请添加课程描述信息...'}
                  </Text>
                </div>

                <div style={{ 
                  background: nodeDocumentIds.length ? '#f0f9ff' : '#fffbe6', 
                  borderRadius: 8, 
                  padding: '10px 16px',
                  border: `1px solid ${nodeDocumentIds.length ? '#91d5ff' : '#ffe58f'}`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  {nodeDocumentIds.length ? (
                    <>
                      <FileTextOutlined style={{ color: '#1890ff', fontSize: 16 }} />
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        已关联 <Text strong style={{ color: '#096dd9' }}>{nodeDocumentIds.length} 个</Text> 知识库文档
                      </Text>
                      <Button 
                        type="link" 
                        size="small" 
                        style={{ marginLeft: 'auto', padding: '0 0 0 8px', height: 20 }}
                        onClick={() => message.info('查看关联文档功能开发中...')}
                      >
                        查看文档
                      </Button>
                    </>
                  ) : (
                    <>
                      <ExclamationCircleOutlined style={{ color: '#faad14', fontSize: 16 }} />
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        未关联任何文档，将使用全局知识库进行问答
                      </Text>
                      <Button 
                        type="link" 
                        size="small" 
                        style={{ marginLeft: 'auto', padding: '0 0 0 8px', height: 20 }}
                        onClick={() => message.info('关联文档功能开发中...')}
                      >
                        去关联
                      </Button>
                    </>
                  )}
                </div>

                <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <Button icon={<UploadOutlined />} onClick={openKnowledgeBaseUpload} loading={uploadingKnowledgeBase}>
                    {isCourseRootSelected ? '导入到课程总目录知识库' : '导入到本知识点知识库'}
                  </Button>
                  <input
                    ref={knowledgeBaseUploadInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    onChange={handleKnowledgeBaseUpload}
                  />
                  <Button type="primary" icon={<MessageOutlined />} onClick={handleJumpToAiStudio}>
                    去 AI 聊一聊
                  </Button>
                </div>
              </div>
              <Divider style={{ margin: '12px 0' }}>智能问答</Divider>
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  marginBottom: 12,
                  minHeight: 0,
                  paddingRight: 6,
                }}
              >
                 {chatMessages.map((msg, i) => (
                   <div key={i} style={{ textAlign: msg.user === 'You' ? 'right' : 'left', marginBottom: 8 }}>
                     <div style={{ display: 'inline-block', padding: '8px 12px', borderRadius: 8, background: msg.user === 'You' ? '#1890ff' : '#f0f0f0', color: msg.user === 'You' ? '#fff' : '#333', maxWidth: '90%', textAlign: 'left' }}>
                        {msg.user === 'AI' ? <ReactMarkdown>{msg.text}</ReactMarkdown> : msg.text}
                     </div>
                   </div>
                 ))}
              </div>
              <Space.Compact style={{ width: '100%', marginBottom: 24 }}>
                <Input.TextArea autoSize={{ minRows: 1, maxRows: 4 }} value={chatInput} onChange={e => setChatInput(e.target.value)} onPressEnter={e => !e.shiftKey && (e.preventDefault(), handleSendChatMessage())} placeholder="输入问题..." />
                <Button type="primary" icon={<MessageOutlined />} loading={chatLoading} onClick={handleSendChatMessage}>发送</Button>
              </Space.Compact>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};

export default KnowledgeGraphPage;
