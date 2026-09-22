type AnchorNode = { type: string; value?: string; children?: AnchorNode[]; tagName?: string; properties?: Record<string, string> };
type Parent = { children: AnchorNode[] };

// Allow only the empty stable section markers emitted by the report contract.
// Other raw HTML remains escaped by ReactMarkdown; code examples are untouched.
export function reportAnchors() {
  return (tree: Parent) => {
    const visit = (parent: Parent) => {
      const result: AnchorNode[] = [];
      for (let i = 0; i < parent.children.length; i++) {
        const node = parent.children[i];
        const next = parent.children[i + 1];
        if (node.type === 'raw') {
          const paired = next?.type === 'raw' && /^\s*<\/a>\s*$/.test(String(next.value));
          const value = String(node.value) + (paired ? String(next.value) : '');
          const match = /^\s*<a\s+id=["']([A-Za-z][A-Za-z0-9_:-]{0,159})["']\s*>\s*<\/a>\s*$/.exec(value);
          if (match) {
            result.push({ type: 'element', tagName: 'a', properties: { id: match[1] }, children: [] });
            if (paired) i++;
            continue;
          }
        }
        if (node.children) {
          const parent = { children: node.children };
          visit(parent);
          node.children = parent.children;
        }
        result.push(node);
      }
      parent.children = result;
    };
    visit(tree);
  };
}
