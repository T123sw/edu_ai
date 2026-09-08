import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { ChatSourceV2 } from '../../services/teacher/chatV2';
import './AnswerMarkdown.css';

export type InlineSourceEntry = { source: ChatSourceV2; order: number };
type MarkdownNode = {
  type: string;
  position?: { start: { offset?: number }; end: { offset?: number } };
  children?: MarkdownNode[];
  data?: { hName: string; hProperties: Record<string, number> };
};

function normalizeSourceComparableText(value: unknown): string {
  return String(value || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*]\(([^)]+)\)/g, ' ')
    .replace(/\[[^\]]*]\(([^)]+)\)/g, ' ')
    .replace(/[*_>#-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}

function buildCharacterBigrams(value: string): string[] {
  const compact = value.replace(/\s+/g, '');
  if (compact.length <= 2) {
    return compact ? [compact] : [];
  }

  const result: string[] = [];
  for (let index = 0; index < compact.length - 1; index += 1) {
    result.push(compact.slice(index, index + 2));
  }
  return result;
}

function scoreSourceBlockMatch(blockText: string, sourceText: string): number {
  const normalizedBlock = normalizeSourceComparableText(blockText);
  const normalizedSource = normalizeSourceComparableText(sourceText);

  if (!normalizedBlock || !normalizedSource) {
    return 0;
  }

  const sourceProbe = normalizedSource.slice(0, Math.min(normalizedSource.length, 36));
  if (sourceProbe && normalizedBlock.includes(sourceProbe)) {
    return 1;
  }

  const sourceBigrams = Array.from(new Set(buildCharacterBigrams(normalizedSource.slice(0, 240))));
  if (sourceBigrams.length === 0) {
    return 0;
  }

  const blockBigramSet = new Set(buildCharacterBigrams(normalizedBlock));
  let overlapCount = 0;
  for (const token of sourceBigrams) {
    if (blockBigramSet.has(token)) {
      overlapCount += 1;
    }
  }

  return overlapCount / sourceBigrams.length;
}


export function AnswerMarkdown({ text, sources, renderSources }: {
  text: string;
  sources: ChatSourceV2[];
  renderSources: (entries: InlineSourceEntry[], blockIndex: number) => ReactNode;
}) {
  const citations = new Map<number, InlineSourceEntry[]>();
  // Attach citations after parsed top-level blocks. Never split or reparse the
  // source text: lists, references, tables and code retain their original AST.
  const attachCitations = () => (tree: { children: MarkdownNode[] }) => {
    citations.clear();
    sources.forEach((source, sourceIndex) => {
      let bestIndex = tree.children.length;
      let bestScore = 0.16;
      tree.children.forEach((node, index) => {
        if (['code', 'math', 'definition', 'footnoteDefinition'].includes(node.type)) return;
        const start = node.position?.start.offset;
        const end = node.position?.end.offset;
        if (start === undefined || end === undefined) return;
        const score = scoreSourceBlockMatch(text.slice(start, end), String(source.content || ''));
        if (score >= bestScore) { bestScore = score; bestIndex = index; }
      });
      const entries = citations.get(bestIndex) || [];
      entries.push({ source, order: sourceIndex + 1 });
      citations.set(bestIndex, entries);
    });
    const marker = (index: number): MarkdownNode => ({
      type: 'paragraph', children: [],
      data: { hName: 'div', hProperties: { 'data-citation-index': index } },
    });
    const end = tree.children.length;
    tree.children = tree.children.flatMap((node, index) => citations.has(index) ? [node, marker(index)] : [node]);
    if (citations.has(end)) tree.children.push(marker(end));
  };
  return <div className="answer-markdown">
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath, attachCitations]} rehypePlugins={[rehypeKatex]}
      components={{
        div: ({ node, children, ...props }) => {
          const index = node?.properties['data-citation-index'];
          if (index !== undefined) return <div className="answer-markdown__citations">{renderSources(citations.get(Number(index)) || [], Number(index))}</div>;
          return <div {...props}>{children}</div>;
        },
        table: ({ children, node: _node, ...props }) => <div className="answer-markdown__table-scroll" role="region" aria-label="回答表格" tabIndex={0}><table {...props}>{children}</table></div>,
        pre: ({ children, node: _node, ...props }) => <pre {...props} tabIndex={0}>{children}</pre>,
      }}>
      {text}
    </ReactMarkdown>
  </div>;
}
