import { useMemo, useState, type CSSProperties } from 'react';
import './MindMapCanvas.css';

export type MindMapNode = {
  id?: string;
  title?: string;
  summary?: string | null;
  children?: MindMapNode[];
};

type Direction = 'left' | 'right';

const branchColors = [
  ['#4f6df5', '#eef2ff'],
  ['#08a88a', '#e9fbf6'],
  ['#e87932', '#fff3e9'],
  ['#a65bd8', '#f8efff'],
  ['#d94f70', '#fff0f4'],
  ['#168ac9', '#eaf7ff'],
  ['#8a9b20', '#f7fae8'],
  ['#7467d6', '#f1efff'],
] as const;

function countNodes(node: MindMapNode): number {
  return 1 + (node.children || []).reduce((total, child) => total + countNodes(child), 0);
}

function expandablePaths(node: MindMapNode, path: string): string[] {
  const children = node.children || [];
  return [
    ...(children.length ? [path] : []),
    ...children.flatMap((child, index) => expandablePaths(child, `${path}.${child.id || index}`)),
  ];
}

function Branch({
  node,
  path,
  index,
  direction,
  depth,
  expanded,
  onToggle,
}: {
  node: MindMapNode;
  path: string;
  index: number;
  direction: Direction;
  depth: number;
  expanded: ReadonlySet<string>;
  onToggle: (path: string) => void;
}) {
  const children = Array.isArray(node.children) ? node.children : [];
  const isExpanded = expanded.has(path);
  const [accent, soft] = branchColors[index % branchColors.length];
  const style = { '--mind-accent': accent, '--mind-soft': soft } as CSSProperties;

  return (
    <li
      className={`balanced-mind-map__branch balanced-mind-map__branch--${direction}`}
      style={style}
      role="treeitem"
      aria-level={depth}
      aria-expanded={children.length ? isExpanded : undefined}
    >
      <article className="balanced-mind-map__node">
        {depth === 2 ? <span className="balanced-mind-map__index">{String(index + 1).padStart(2, '0')}</span> : null}
        <strong>{node.title || '未命名节点'}</strong>
        {node.summary ? <small>{node.summary}</small> : null}
        {children.length ? (
          <button
            type="button"
            className="balanced-mind-map__toggle"
            aria-label={`${isExpanded ? '收起' : '展开'}${node.title || '节点'}`}
            onClick={() => onToggle(path)}
          >
            <span aria-hidden="true">{isExpanded ? '−' : '+'}</span>
            {isExpanded ? '收起' : `${children.length} 个要点`}
          </button>
        ) : null}
      </article>
      {children.length && isExpanded ? (
        <ol className="balanced-mind-map__children" role="group">
          {children.map((child, childIndex) => (
            <Branch
              key={child.id || `${child.title}-${childIndex}`}
              node={child}
              path={`${path}.${child.id || childIndex}`}
              index={index}
              direction={direction}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
            />
          ))}
        </ol>
      ) : null}
    </li>
  );
}

export function MindMapCanvas({
  root,
  label,
  onExport,
}: {
  root: MindMapNode | null;
  label: string;
  onExport?: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const children = useMemo(
    () => root && Array.isArray(root.children) ? root.children : [],
    [root],
  );
  const middle = Math.ceil(children.length / 2);
  const left = children.slice(0, middle);
  const right = children.slice(middle);
  const nodeCount = useMemo(() => root ? countNodes(root) : 0, [root]);
  const allExpandable = useMemo(
    () => children.flatMap((child, index) => expandablePaths(child, `root.${child.id || index}`)),
    [children],
  );

  const toggle = (path: string) => setExpanded((current) => {
    const next = new Set(current);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    return next;
  });

  const reset = () => {
    setZoom(1);
    setExpanded(new Set());
  };

  return (
    <section className="balanced-mind-map" aria-label={`${label}导图预览`}>
      <header className="balanced-mind-map__toolbar">
        <div className="balanced-mind-map__view-controls" aria-label="节点显示范围">
          <button type="button" className={expanded.size === 0 ? 'is-active' : ''} onClick={() => setExpanded(new Set())}>概览</button>
          <button type="button" className={expanded.size === allExpandable.length && allExpandable.length ? 'is-active' : ''} disabled={!allExpandable.length} onClick={() => setExpanded(new Set(allExpandable))}>展开全部</button>
        </div>
        <span className="balanced-mind-map__stats">{children.length} 个主分支 · {nodeCount} 个节点</span>
        <div className="balanced-mind-map__zoom-controls">
          <button type="button" aria-label="缩小" onClick={() => setZoom((value) => Math.max(0.6, value - 0.1))}>−</button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="放大" onClick={() => setZoom((value) => Math.min(1.6, value + 0.1))}>+</button>
          <button type="button" aria-label="复位" className="balanced-mind-map__reset" onClick={reset}>复位</button>
          {onExport ? <button type="button" className="balanced-mind-map__export" onClick={onExport}>导出导图</button> : null}
        </div>
      </header>
      <div className="balanced-mind-map__viewport">
        {root ? (
          <div className="balanced-mind-map__scale" style={{ transform: `scale(${zoom})` }}>
            <div className="balanced-mind-map__diagram" role="tree" aria-label={label}>
              <ol className="balanced-mind-map__side balanced-mind-map__side--left" role="group">
                {left.map((child, index) => (
                  <Branch key={child.id || `${child.title}-${index}`} node={child} path={`root.${child.id || index}`} index={index} direction="left" depth={2} expanded={expanded} onToggle={toggle} />
                ))}
              </ol>
              <article className="balanced-mind-map__root" role="treeitem" aria-level={1}>
                <span>中心主题</span>
                <strong>{root.title || '未命名主题'}</strong>
                {root.summary ? <small>{root.summary}</small> : null}
              </article>
              <ol className="balanced-mind-map__side balanced-mind-map__side--right" role="group">
                {right.map((child, offset) => {
                  const index = middle + offset;
                  return <Branch key={child.id || `${child.title}-${index}`} node={child} path={`root.${child.id || index}`} index={index} direction="right" depth={2} expanded={expanded} onToggle={toggle} />;
                })}
              </ol>
            </div>
          </div>
        ) : <p className="resource-preview-empty">当前思维导图暂无节点。</p>}
      </div>
    </section>
  );
}
