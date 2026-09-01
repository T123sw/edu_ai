import type { KnowledgeGraphNode } from "../../api/types";

export type GraphDraftStats = {
  nodeCount: number;
  moduleCount: number;
  leafCount: number;
  maxDepth: number;
  mappedOutlineCount: number;
  unmappedOutlineCount: number;
};

export type GraphNodeOption = {
  id: string;
  label: string;
  depth: number;
  parentId: string | null;
};

export type GraphReviewFilter = "all" | "new" | "issues" | "mapped";

export type GraphReviewIssue = {
  code: "missing_content" | "needs_parent";
  nodeId: string;
  message: string;
  severity: "error" | "warning";
};

export type GraphReviewNode = GraphNodeOption & {
  node: KnowledgeGraphNode;
  childCount: number;
  isExisting: boolean;
  isNew: boolean;
  isMapped: boolean;
  hasIssue: boolean;
};

export type GraphReviewModel = {
  orderedIds: string[];
  nodesById: Map<string, GraphReviewNode>;
  issues: GraphReviewIssue[];
  initialSelectedNodeId: string;
};

function clone(node: KnowledgeGraphNode): KnowledgeGraphNode {
  return {
    ...node,
    data: node.data ? { ...node.data, source_outline_refs: [...(node.data.source_outline_refs || [])] } : {},
    children: (node.children || []).map(clone),
  };
}

function normalize(root: KnowledgeGraphNode): KnowledgeGraphNode {
  function visit(node: KnowledgeGraphNode, depth: number): KnowledgeGraphNode {
    const children = (node.children || []).map((child) => visit(child, depth + 1));
    const type = depth === 1
      ? "course"
      : children.length === 0
        ? "knowledge_point"
        : depth === 2
          ? "knowledge_module"
          : "knowledge_unit";
    return {
      ...node,
      data: { ...(node.data || {}), level: depth - 1, type, hasChildren: children.length > 0 },
      children,
    };
  }
  return visit(root, 1);
}

export function updateGraphNode(
  root: KnowledgeGraphNode,
  nodeId: string,
  patch: { label?: string; summary?: string; sourceOutlineRefs?: string[] },
) {
  const next = clone(root);
  function visit(node: KnowledgeGraphNode) {
    if (node.id === nodeId) {
      if (patch.label !== undefined) node.label = patch.label;
      if (patch.summary !== undefined) node.data = { ...(node.data || {}), summary: patch.summary };
      if (patch.sourceOutlineRefs !== undefined) {
        node.data = { ...(node.data || {}), source_outline_refs: [...patch.sourceOutlineRefs] };
      }
      return true;
    }
    return (node.children || []).some(visit);
  }
  visit(next);
  return normalize(next);
}

export function removeGraphNode(root: KnowledgeGraphNode, nodeId: string) {
  if (root.id === nodeId) return root;
  const next = clone(root);
  function visit(node: KnowledgeGraphNode): boolean {
    const children = node.children || [];
    const index = children.findIndex((child) => child.id === nodeId);
    if (index >= 0) {
      children.splice(index, 1);
      return true;
    }
    return children.some(visit);
  }
  visit(next);
  return normalize(next);
}

function uniqueId(root: KnowledgeGraphNode) {
  const ids = new Set(graphNodeOptions(root).map((item) => item.id));
  let suffix = 1;
  while (ids.has(`draft-node-${suffix}`)) suffix += 1;
  return `draft-node-${suffix}`;
}

export function addGraphChild(root: KnowledgeGraphNode, parentId: string, maxDepth: number) {
  const next = clone(root);
  const newId = uniqueId(root);
  function visit(node: KnowledgeGraphNode, depth: number): boolean {
    if (node.id === parentId) {
      if (depth >= maxDepth) return false;
      node.children = [
        ...(node.children || []),
        {
          id: newId,
          label: "待命名知识节点",
          data: { summary: "请补充这个知识节点的课程说明。" },
          children: [],
        },
      ];
      return true;
    }
    return (node.children || []).some((child) => visit(child, depth + 1));
  }
  const added = visit(next, 1);
  return { root: normalize(next), addedId: added ? newId : null };
}

export function moveGraphSibling(root: KnowledgeGraphNode, nodeId: string, direction: -1 | 1) {
  const next = clone(root);
  function visit(node: KnowledgeGraphNode): boolean {
    const children = node.children || [];
    const index = children.findIndex((child) => child.id === nodeId);
    if (index >= 0) {
      const destination = index + direction;
      if (destination < 0 || destination >= children.length) return false;
      [children[index], children[destination]] = [children[destination], children[index]];
      return true;
    }
    return children.some(visit);
  }
  visit(next);
  return normalize(next);
}

export function graphNodeOptions(root: KnowledgeGraphNode): GraphNodeOption[] {
  const result: GraphNodeOption[] = [];
  function visit(node: KnowledgeGraphNode, depth: number, parentId: string | null) {
    result.push({ id: node.id, label: node.label, depth, parentId });
    (node.children || []).forEach((child) => visit(child, depth + 1, node.id));
  }
  visit(root, 1, null);
  return result;
}

function contains(node: KnowledgeGraphNode, id: string): boolean {
  return node.id === id || (node.children || []).some((child) => contains(child, id));
}

export function moveGraphNode(root: KnowledgeGraphNode, nodeId: string, newParentId: string) {
  const options = graphNodeOptions(root);
  const source = options.find((item) => item.id === nodeId);
  const target = options.find((item) => item.id === newParentId);
  if (!source?.parentId || !target || target.depth !== source.depth - 1) return root;

  const next = clone(root);
  let moving: KnowledgeGraphNode | null = null;
  function detach(node: KnowledgeGraphNode): boolean {
    const children = node.children || [];
    const index = children.findIndex((child) => child.id === nodeId);
    if (index >= 0) {
      moving = children.splice(index, 1)[0];
      return true;
    }
    return children.some(detach);
  }
  detach(next);
  if (!moving || contains(moving, newParentId)) return root;
  function attach(node: KnowledgeGraphNode): boolean {
    if (node.id === newParentId) {
      node.children = [...(node.children || []), moving as KnowledgeGraphNode];
      return true;
    }
    return (node.children || []).some(attach);
  }
  return attach(next) ? normalize(next) : root;
}

export function graphDraftStats(root: KnowledgeGraphNode): GraphDraftStats {
  let nodeCount = 0;
  let leafCount = 0;
  let maxDepth = 0;
  const mapped = new Set<string>();
  function visit(node: KnowledgeGraphNode, depth: number) {
    nodeCount += 1;
    maxDepth = Math.max(maxDepth, depth);
    if (!(node.children || []).length) leafCount += 1;
    (node.data?.source_outline_refs || []).forEach((item) => mapped.add(item));
    (node.children || []).forEach((child) => visit(child, depth + 1));
  }
  visit(root, 1);
  return {
    nodeCount,
    moduleCount: root.children?.length || 0,
    leafCount,
    maxDepth,
    mappedOutlineCount: mapped.size,
    unmappedOutlineCount: root.data?.unmapped_outline_items?.length || 0,
  };
}

export function graphDraftEqual(left: KnowledgeGraphNode, right: KnowledgeGraphNode) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function findGraphNode(root: KnowledgeGraphNode, nodeId: string): KnowledgeGraphNode | null {
  if (root.id === nodeId) return root;
  for (const child of root.children || []) {
    const found = findGraphNode(child, nodeId);
    if (found) return found;
  }
  return null;
}

export function canEditGraphNodeStructure(nodeId: string, baseline: KnowledgeGraphNode | null) {
  return !baseline || !findGraphNode(baseline, nodeId);
}

export function buildGraphReviewModel(
  root: KnowledgeGraphNode,
  baseline: KnowledgeGraphNode | null,
): GraphReviewModel {
  const baselineIds = new Set(baseline ? graphNodeOptions(baseline).map((item) => item.id) : []);
  const orderedIds: string[] = [];
  const nodesById = new Map<string, GraphReviewNode>();
  const issues: GraphReviewIssue[] = [];

  function visit(node: KnowledgeGraphNode, depth: number, parentId: string | null) {
    orderedIds.push(node.id);
    const isExisting = baselineIds.has(node.id);
    const summary = (node.data?.summary || "").trim();
    if (!node.label.trim() || !summary) {
      issues.push({
        code: "missing_content",
        nodeId: node.id,
        message: `${node.label || "未命名节点"}缺少名称或说明`,
        severity: "warning",
      });
    }
    if (node.data?.review_state === "needs_parent" || node.data?.needs_parent) {
      issues.push({
        code: "needs_parent",
        nodeId: node.id,
        message: `${node.label || "未命名节点"}尚未选择父节点`,
        severity: "error",
      });
    }
    nodesById.set(node.id, {
      id: node.id,
      label: node.label,
      depth,
      parentId,
      node,
      childCount: node.children?.length || 0,
      isExisting,
      isNew: !isExisting,
      isMapped: Boolean(node.data?.source_outline_refs?.length),
      hasIssue: false,
    });
    (node.children || []).forEach((child) => visit(child, depth + 1, node.id));
  }

  visit(root, 1, null);
  for (const issue of issues) {
    const item = nodesById.get(issue.nodeId);
    if (item) item.hasIssue = true;
  }
  return {
    orderedIds,
    nodesById,
    issues,
    initialSelectedNodeId: issues[0]?.nodeId || root.id,
  };
}

export function ancestorNodeIds(model: GraphReviewModel, nodeId: string) {
  const result: string[] = [];
  let current = model.nodesById.get(nodeId);
  while (current?.parentId) {
    result.unshift(current.parentId);
    current = model.nodesById.get(current.parentId);
  }
  return result;
}

export function visibleGraphNodeIds(
  model: GraphReviewModel,
  query: string,
  filter: GraphReviewFilter,
) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matches = new Set<string>();
  for (const nodeId of model.orderedIds) {
    const item = model.nodesById.get(nodeId);
    if (!item) continue;
    const matchesQuery = !normalizedQuery
      || item.label.toLocaleLowerCase().includes(normalizedQuery);
    const matchesFilter = filter === "all"
      || (filter === "new" && item.isNew)
      || (filter === "issues" && item.hasIssue)
      || (filter === "mapped" && item.isMapped);
    if (!matchesQuery || !matchesFilter) continue;
    matches.add(nodeId);
    ancestorNodeIds(model, nodeId).forEach((id) => matches.add(id));
  }
  return model.orderedIds.filter((id) => matches.has(id));
}
