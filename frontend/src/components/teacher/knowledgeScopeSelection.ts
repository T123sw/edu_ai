export type KnowledgeScopeNode = {
  id: string;
  children?: KnowledgeScopeNode[];
};

export function collectKnowledgeSubtreeNodeIds(
  node: KnowledgeScopeNode,
): string[] {
  return [
    node.id,
    ...(node.children || []).flatMap(collectKnowledgeSubtreeNodeIds),
  ];
}

export function collectScopedKnowledgeNodeIds(
  root: KnowledgeScopeNode | null,
  scopeId?: string,
): string[] {
  if (!root || !scopeId) return [];
  if (root.id === scopeId) return collectKnowledgeSubtreeNodeIds(root);

  for (const child of root.children || []) {
    const matched = collectScopedKnowledgeNodeIds(child, scopeId);
    if (matched.length > 0) return matched;
  }
  return [];
}
