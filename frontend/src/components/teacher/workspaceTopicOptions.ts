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
