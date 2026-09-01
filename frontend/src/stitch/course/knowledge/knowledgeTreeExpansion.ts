import type { KnowledgeGraphNode } from "../../api/types";

export type KnowledgeTreeEntry = KnowledgeGraphNode & {
  depth: number;
  parentId: string | null;
};

export function defaultExpandedNodeIds(root: KnowledgeGraphNode | null): Set<string> {
  return root ? new Set([root.id]) : new Set();
}

export function flattenKnowledgeTree(
  node: KnowledgeGraphNode,
  parentId: string | null = null,
  depth = 0,
): KnowledgeTreeEntry[] {
  return [
    { ...node, parentId, depth },
    ...(node.children ?? []).flatMap((child) => flattenKnowledgeTree(child, node.id, depth + 1)),
  ];
}

export function visibleKnowledgeTree(
  node: KnowledgeGraphNode,
  expandedIds: ReadonlySet<string>,
  parentId: string | null = null,
  depth = 0,
): KnowledgeTreeEntry[] {
  const current = { ...node, parentId, depth };
  if (!expandedIds.has(node.id)) return [current];
  return [
    current,
    ...(node.children ?? []).flatMap((child) => visibleKnowledgeTree(child, expandedIds, node.id, depth + 1)),
  ];
}

export function descendantNodeIds(node: KnowledgeGraphNode): Set<string> {
  return new Set((node.children ?? []).flatMap((child) => [child.id, ...descendantNodeIds(child)]));
}

export function toggleExpandedNode(
  expandedIds: ReadonlySet<string>,
  node: KnowledgeGraphNode,
): Set<string> {
  const next = new Set(expandedIds);
  if (next.has(node.id)) {
    next.delete(node.id);
    descendantNodeIds(node).forEach((id) => next.delete(id));
  } else {
    next.add(node.id);
  }
  return next;
}
