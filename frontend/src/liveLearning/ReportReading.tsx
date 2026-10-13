import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { reportBlockId, reportFingerprint } from './reportReading';
import { normalizeKnowledgeMarkdown } from '../stitch/components/knowledgeMarkdown';
import type { Locator } from './readingContext';
import './reportReading.css';

const selector = '[data-report-start][data-report-end]';
type Target = { range: Range; start: number; end: number; text: string; block: HTMLElement };
type Highlights = { set: (name: string, highlight: unknown) => void; delete: (name: string) => void };
function highlights() { return (globalThis.CSS as typeof CSS & { highlights?: Highlights })?.highlights; }

export function ReportReading({ markdown, children, clearSignal, onReference, initialBlockId, enabled = true }: {
  markdown: string; children: ReactNode; clearSignal: number;
  initialBlockId?: string; enabled?: boolean;
  onReference: (text: string, locator: Locator, intent?: 'ask') => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const toolbar = useRef<HTMLDivElement>(null);
  const chosen = useRef<Target>();
  const active = useRef<Target>();
  const callbacks = useRef(onReference);
  callbacks.current = onReference;
  const [position, setPosition] = useState<{ top: number; left: number }>();
  const [error, setError] = useState('');

  useEffect(() => {
    if (!initialBlockId || !root.current) return;
    const source = normalizeKnowledgeMarkdown(markdown);
    const match = /^report-v1:(\d+):(\d+):([0-9a-f]{8})$/.exec(initialBlockId);
    if (!match || match[3] !== reportFingerprint(source) || +match[1] >= +match[2] || +match[2] > Array.from(source).length) {
      setError('引用段落位置不可用，已打开原版本资料。'); return;
    }
    const start = Array.from(source).slice(0, +match[1]).join('').length;
    const end = Array.from(source).slice(0, +match[2]).join('').length;
    const blocks = [...root.current.querySelectorAll<HTMLElement>(selector)].filter(el => Number(el.dataset.reportStart) < end && Number(el.dataset.reportEnd) > start);
    if (!blocks.length) { setError('未能定位引用段落，已打开原版本资料。'); return; }
    blocks.forEach(el => el.classList.add('report-reference-fallback'));
    blocks[0].scrollIntoView({ block: 'center' });
    return () => blocks.forEach(el => el.classList.remove('report-reference-fallback'));
  }, [markdown, initialBlockId]);

  const locate = useCallback((target: Target) => {
    active.current = target;
    const rect = target.range.getBoundingClientRect();
    setPosition({ top: Math.max(4, Math.min(innerHeight - 42, rect.top - 35)), left: Math.max(4, Math.min(innerWidth - 100, rect.right - 86)) });
  }, []);

  const reference = useCallback((target: Target, intent?: 'ask') => {
    if (target.text.length > 10000) {
      chosen.current = undefined;
      highlights()?.delete('learning-reference');
      root.current?.querySelectorAll('.report-reference-fallback').forEach(el => el.classList.remove('report-reference-fallback'));
      callbacks.current('', { kind: 'document', scroll_top: scrollY });
      setError('选中内容较长，请缩小范围后提问。');
      return;
    }
    chosen.current = target;
    root.current?.querySelectorAll('.report-reference-fallback').forEach(el => el.classList.remove('report-reference-fallback'));
    const Highlight = (globalThis as unknown as { Highlight?: new (...ranges: Range[]) => unknown }).Highlight;
    if (Highlight && highlights()) highlights()!.set('learning-reference', new Highlight(target.range));
    else target.block.classList.add('report-reference-fallback');
    setError('');
    callbacks.current(target.text, { kind: 'document', scroll_top: scrollY, block_id: reportBlockId(markdown, target.start, target.end) }, intent);
  }, [markdown]);

  useEffect(() => {
    if (!enabled) return;
    const selection = () => {
      const selected = window.getSelection();
      if (!selected || selected.isCollapsed || !selected.rangeCount || !root.current) return;
      const range = selected.getRangeAt(0);
      if (!root.current.contains(range.startContainer) || !root.current.contains(range.endContainer)) return;
      const blocks = [...root.current.querySelectorAll<HTMLElement>(selector)].filter(el => range.intersectsNode(el));
      // For nested blocks use the smallest enclosing source spans at each endpoint.
      const endpoint = (node: Node) => (node instanceof Element ? node : node.parentElement)?.closest<HTMLElement>(selector);
      const first = endpoint(range.startContainer) || blocks[0], last = endpoint(range.endContainer) || blocks.at(-1);
      if (!first || !last || !selected.toString().trim()) return;
      const target = { range: range.cloneRange(), start: Math.min(Number(first.dataset.reportStart), Number(last.dataset.reportStart)),
        end: Math.max(Number(first.dataset.reportEnd), Number(last.dataset.reportEnd)), text: selected.toString().trim(), block: first };
      locate(target);
      reference(target);
    };
    const moved = () => { if (chosen.current) locate(chosen.current); else setPosition(undefined); };
    document.addEventListener('selectionchange', selection);
    window.addEventListener('scroll', moved, true);
    window.addEventListener('resize', moved);
    return () => { document.removeEventListener('selectionchange', selection); window.removeEventListener('scroll', moved, true); window.removeEventListener('resize', moved); highlights()?.delete('learning-reference'); };
  }, [locate, reference, enabled]);

  useEffect(() => {
    if (!clearSignal) return;
    chosen.current = undefined;
    active.current = undefined;
    highlights()?.delete('learning-reference');
    root.current?.querySelectorAll('.report-reference-fallback').forEach(el => el.classList.remove('report-reference-fallback'));
    window.getSelection()?.removeAllRanges();
    setPosition(undefined);
    callbacks.current('', { kind: 'document', scroll_top: scrollY });
  }, [clearSignal]);

  const hover = (node: EventTarget | null) => {
    if (!enabled) return;
    const block = node instanceof Element ? node.closest<HTMLElement>(selector) : null;
    if (!block || !root.current?.contains(block) || window.getSelection()?.toString()) return;
    const range = document.createRange();
    range.selectNodeContents(block);
    const text = range.toString().trim();
    if (text) locate({ block, range, text, start: Number(block.dataset.reportStart), end: Number(block.dataset.reportEnd) });
  };

  return <>
    <div ref={root} className="report-reading" onPointerOver={e => hover(e.target)} onFocus={e => hover(e.target)}
      onPointerLeave={e => { if (!(e.relatedTarget instanceof Node && toolbar.current?.contains(e.relatedTarget)) && !chosen.current) setPosition(undefined); }}>
      {children}
    </div>
    {position && <div ref={toolbar} className="report-ai-toolbar" style={position} role="toolbar" aria-label="报告片段操作">
      <button type="button" onPointerDown={e => e.preventDefault()} onClick={() => { if (active.current) reference(active.current, 'ask'); }}><span aria-hidden="true">✦</span> 问 AI</button>
    </div>}
    {error && <p className="report-selection-error" role="alert">{error}</p>}
  </>;
}
