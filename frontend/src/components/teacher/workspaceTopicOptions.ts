export interface WorkspaceTopicOption {
  value: string;
  label: string;
  title: string;
}

/** Offer specific topics directly, keeping their full paths for search and tooltips. */
export function getWorkspaceTopicOptions(root: unknown): WorkspaceTopicOption[] {
  const options: WorkspaceTopicOption[] = [];
  function visit(node: unknown, path: string[], isRoot = false) {
    if (!node || typeof node !== 'object') return;
    const value = node as { id?: unknown; label?: unknown; children?: unknown[] };
    const label = String(value.label || '').trim();
    const nextPath = label ? [...path, label] : path;
    const children = Array.isArray(value.children) ? value.children : [];
    if (!isRoot && children.length === 0 && value.id && label) {
      options.push({ value: String(value.id), label, title: nextPath.join(' › ') });
    }
    children.forEach((child) => visit(child, nextPath));
  }
  visit(root, [], true);
  return options;
}

export interface WorkspaceTopicNode {
  value: string;
  title: string;
  path: string;
  selectable: boolean;
  children?: WorkspaceTopicNode[];
}

export function getWorkspaceTopicTree(root: unknown): WorkspaceTopicNode[] {
  function visit(node: unknown, path: string[], isRoot = false): WorkspaceTopicNode | undefined {
    if (!node || typeof node !== 'object') return;
    const value = node as { id?: unknown; label?: unknown; children?: unknown[] };
    const title = String(value.label || '').trim();
    if (!value.id || !title) return;
    const nextPath = [...path, title];
    const children = (Array.isArray(value.children) ? value.children : [])
      .map(child => visit(child, nextPath)).filter((child): child is WorkspaceTopicNode => Boolean(child));
    return { value: String(value.id), title, path: nextPath.join(' › '),
      selectable: !isRoot && children.length === 0, ...(children.length ? { children } : {}) };
  }
  const tree = visit(root, [], true);
  return tree ? [tree] : [];
}

export function getWorkspaceTopicAncestors(nodes: WorkspaceTopicNode[], value?: string): string[] {
  for (const node of nodes) {
    if (node.value === value) return [];
    if (node.children) {
      if (node.children.some(child => child.value === value)) return [node.value];
      const ancestors = getWorkspaceTopicAncestors(node.children, value);
      if (ancestors.length) return [node.value, ...ancestors];
    }
  }
  return [];
}
