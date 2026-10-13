import { normalizeKnowledgeMarkdown } from '../stitch/components/knowledgeMarkdown';

// A version-bound rendering fingerprint, not an authorization/security hash.
export function reportFingerprint(text: string): string {
  let hash = 2166136261;
  for (const byte of new TextEncoder().encode(text)) hash = Math.imul(hash ^ byte, 16777619) >>> 0;
  return hash.toString(16).padStart(8, '0');
}

export function reportBlockId(markdown: string, start: number, end: number): string {
  const source = normalizeKnowledgeMarkdown(markdown);
  return `report-v1:${Array.from(source.slice(0, start)).length}:${Array.from(source.slice(0, end)).length}:${reportFingerprint(source)}`;
}

type Node = { type: string; tagName?: string; properties?: Record<string, unknown>; position?: { start: { offset?: number }; end: { offset?: number } }; children?: Node[] };
export function reportReadingAnchors() {
  return (tree: Node) => {
    const visit = (node: Node) => {
      const start = node.position?.start.offset, end = node.position?.end.offset;
      if (node.type === 'element' && /^(p|li|pre|blockquote|table|h[1-6])$/.test(node.tagName || '') && start !== undefined && end !== undefined) {
        node.properties = { ...node.properties, 'data-report-start': start, 'data-report-end': end, tabIndex: 0 };
      }
      node.children?.forEach(visit);
    };
    visit(tree);
  };
}
