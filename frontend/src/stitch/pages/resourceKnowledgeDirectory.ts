import type { CourseMaterial, KnowledgeGraphNode } from "../api/types";

export type ResourceDirectoryNode = {
  id: string;
  kind: "knowledge" | "collection";
  label: string;
  materials: CourseMaterial[];
  children: ResourceDirectoryNode[];
  count: number;
};

/** Prefer persisted associations; only use an unambiguous exact topic for older resources. */
export function buildResourceDirectory(root: KnowledgeGraphNode | null, materials: CourseMaterial[]): ResourceDirectoryNode[] {
  const byId = new Map<string, ResourceDirectoryNode>();
  const byLabel = new Map<string, ResourceDirectoryNode[]>();
  function visit(node: KnowledgeGraphNode): ResourceDirectoryNode {
    const result: ResourceDirectoryNode = { id: node.id, kind: "knowledge", label: node.label, materials: [], children: [], count: 0 };
    byId.set(node.id, result);
    const label = node.label.trim();
    byLabel.set(label, [...(byLabel.get(label) || []), result]);
    result.children = (node.children || []).map(visit);
    return result;
  }
  const nodes = root ? [visit(root)] : [];
  const unclassified: ResourceDirectoryNode = { id: "resource-unclassified", kind: "collection", label: "未分类资源", materials: [], children: [], count: 0 };
  for (const material of materials) {
    const matches = byLabel.get(material.topic?.trim() || "");
    const target = material.scope_type === "course" && root
      ? byId.get(root.id)
      : material.scope_id
        ? byId.get(material.scope_id)
        : matches?.length === 1 ? matches[0] : undefined;
    (target || unclassified).materials.push(material);
  }
  if (unclassified.materials.length) nodes.push(unclassified);
  function organize(node: ResourceDirectoryNode, isRoot = false): number {
    const childCount = node.children.reduce((sum, child) => sum + organize(child), 0);
    node.count = node.materials.length + childCount;
    // Keep knowledge branches first so a large collection cannot bury the curriculum.
    if (node.kind === "knowledge" && (isRoot || node.children.length) && node.materials.length) {
      node.children.push({
        id: `resource-collection:${node.id}`,
        kind: "collection",
        label: isRoot ? "课程资源" : "本节资源",
        materials: node.materials,
        children: [],
        count: node.materials.length,
      });
      node.materials = [];
    }
    return node.count;
  }
  nodes.forEach(node => organize(node, node.id === root?.id));
  return nodes;
}
