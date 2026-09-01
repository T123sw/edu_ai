export type EditableMindMapNode = {
  id: string;
  title: string;
  children: EditableMindMapNode[];
};

function mapNode(
  node: EditableMindMapNode,
  nodeId: string,
  transform: (node: EditableMindMapNode) => EditableMindMapNode,
): EditableMindMapNode {
  if (node.id === nodeId) return transform(node);
  return {
    ...node,
    children: node.children.map((child) => mapNode(child, nodeId, transform)),
  };
}

export function updateMindMapNodeTitle(
  root: EditableMindMapNode,
  nodeId: string,
  title: string,
): EditableMindMapNode {
  return mapNode(root, nodeId, (node) => ({ ...node, title }));
}

export function addMindMapChild(
  root: EditableMindMapNode,
  parentId: string,
): EditableMindMapNode {
  return mapNode(root, parentId, (node) => {
    const used = new Set(node.children.map((child) => child.id));
    let index = node.children.length + 1;
    let id = `${node.id}-${index}`;
    while (used.has(id)) {
      index += 1;
      id = `${node.id}-${index}`;
    }
    return {
      ...node,
      children: [...node.children, { id, title: "新节点", children: [] }],
    };
  });
}

export function removeMindMapNode(
  root: EditableMindMapNode,
  nodeId: string,
): EditableMindMapNode {
  if (root.id === nodeId) return root;
  return {
    ...root,
    children: root.children
      .filter((child) => child.id !== nodeId)
      .map((child) => removeMindMapNode(child, nodeId)),
  };
}
