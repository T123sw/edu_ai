import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent } from 'react';
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
      <article
        className="balanced-mind-map__node"
        title={node.summary || undefined}
        role={children.length ? 'button' : undefined}
        tabIndex={children.length ? 0 : undefined}
        aria-label={children.length ? `${isExpanded ? '收起' : '展开'}${node.title || '节点'}` : undefined}
        aria-expanded={children.length ? isExpanded : undefined}
        onClick={children.length ? () => onToggle(path) : undefined}
        onKeyDown={children.length ? event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            if (!event.repeat) onToggle(path);
          }
        } : undefined}
      >
        {depth === 2 ? <span className="balanced-mind-map__index">{String(index + 1).padStart(2, '0')}</span> : null}
        <strong>{node.title || '未命名节点'}</strong>
        {node.summary ? <small>{node.summary}</small> : null}
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
  const sectionRef = useRef<HTMLElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const diagramRef = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState('');
  const [camera, setCamera] = useState<{ zoom: number | null; x: number; y: number }>({ zoom: null, x: 0, y: 0 });
  const dragRef = useRef<{ pointerId: number; x: number; y: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [layout, setLayout] = useState({ width: 1, height: 1, viewportWidth: 1, viewportHeight: 1, edges: [] as { path: string; color: string }[] });
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [rootCollapsed, setRootCollapsed] = useState(false);
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

  useEffect(() => {
    const syncFullscreen = () => {
      setFullscreen(document.fullscreenElement === sectionRef.current);
      setCamera({ zoom: null, x: 0, y: 0 });
    };
    document.addEventListener('fullscreenchange', syncFullscreen);
    return () => document.removeEventListener('fullscreenchange', syncFullscreen);
  }, []);

  const toggleFullscreen = async () => {
    setFullscreenError('');
    try {
      if (document.fullscreenElement === sectionRef.current) await document.exitFullscreen();
      else await sectionRef.current?.requestFullscreen();
    } catch {
      setFullscreenError('暂时无法进入全屏，请使用滚轮或缩放按钮查看。');
    }
  };

  // Measure unscaled layout coordinates: CSS transforms must not affect either
  // the fitted zoom or the positions of links between unequal-depth branches.
  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    const diagram = diagramRef.current;
    if (!viewport || !diagram) return;
    const measure = () => {
      const position = (element: HTMLElement) => {
        let x = 0;
        let y = 0;
        let current: HTMLElement | null = element;
        while (current && current !== diagram) {
          x += current.offsetLeft;
          y += current.offsetTop;
          current = current.offsetParent as HTMLElement | null;
        }
        return { x, y: y + element.offsetHeight / 2, width: element.offsetWidth };
      };
      const rootNode = diagram.querySelector<HTMLElement>('.balanced-mind-map__root');
      const edges: { path: string; color: string }[] = [];
      diagram.querySelectorAll<HTMLElement>('.balanced-mind-map__branch').forEach((branch) => {
        const node = branch.querySelector<HTMLElement>(':scope > .balanced-mind-map__node');
        const parentBranch = branch.parentElement?.closest('.balanced-mind-map__branch');
        const parent = parentBranch?.querySelector<HTMLElement>(':scope > .balanced-mind-map__node') || rootNode;
        if (!node || !parent) return;
        const leftward = branch.classList.contains('balanced-mind-map__branch--left');
        const from = position(parent);
        const to = position(node);
        const x1 = from.x + (leftward ? 0 : from.width);
        const x2 = to.x + (leftward ? to.width : 0);
        const middleX = (x1 + x2) / 2;
        edges.push({
          path: `M ${x1} ${from.y} C ${middleX} ${from.y}, ${middleX} ${to.y}, ${x2} ${to.y}`,
          color: getComputedStyle(branch).getPropertyValue('--mind-accent').trim(),
        });
      });
      setLayout({ width: diagram.offsetWidth, height: diagram.offsetHeight, viewportWidth: viewport.clientWidth, viewportHeight: viewport.clientHeight, edges });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(viewport);
    observer.observe(diagram);
    return () => observer.disconnect();
  }, [root, expanded, rootCollapsed]);

  const fitZoom = Math.min(1, Math.max(1, layout.viewportWidth - 48) / layout.width, Math.max(1, layout.viewportHeight - 48) / layout.height);
  const zoom = camera.zoom ?? fitZoom;
  const zoomAt = useCallback((factor: number, point?: { x: number; y: number }) => {
    setCamera(current => {
      const previousZoom = current.zoom ?? fitZoom;
      const nextZoom = Math.min(3, Math.max(Math.min(fitZoom, 0.1), previousZoom * factor));
      const ratio = nextZoom / previousZoom;
      // Keep the world point beneath the cursor stationary, even after panning.
      const x = point ? point.x - layout.viewportWidth / 2 : 0;
      const y = point ? point.y - layout.viewportHeight / 2 : 0;
      return { zoom: nextZoom, x: x - (x - current.x) * ratio, y: y - (y - current.y) * ratio };
    });
  }, [fitZoom, layout.viewportWidth, layout.viewportHeight]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || !root) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      const bounds = viewport.getBoundingClientRect();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1;
      const delta = Math.max(-120, Math.min(120, event.deltaY * unit));
      zoomAt(Math.exp(-delta * 0.002), { x: event.clientX - bounds.left - viewport.clientLeft, y: event.clientY - bounds.top - viewport.clientTop });
    };
    viewport.addEventListener('wheel', wheel, { passive: false });
    return () => viewport.removeEventListener('wheel', wheel);
  }, [root, zoomAt]);

  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!root || !event.isPrimary || event.button !== 0 || (event.target as HTMLElement).closest('button, a, input, textarea, select')) return;
    suppressClickRef.current = false;
    // Capture only after real movement so a press/release still clicks the node.
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
  };

  const moveDrag = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    if (!drag.moved) {
      event.currentTarget.setPointerCapture(event.pointerId);
      event.currentTarget.focus({ preventScroll: true });
      suppressClickRef.current = true;
      setDragging(true);
    }
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY, moved: true };
    setCamera(current => ({ ...current, x: current.x + dx, y: current.y + dy }));
  };

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const fit = () => setCamera({ zoom: null, x: 0, y: 0 });

  const showNodes = (paths: string[]) => {
    setRootCollapsed(false);
    setExpanded(new Set(paths));
    fit();
  };

  const toggle = (path: string) => {
    fit();
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const reset = () => {
    showNodes([]);
  };

  return (
    <section ref={sectionRef} className="balanced-mind-map" aria-label={`${label}导图预览`}>
      <header className="balanced-mind-map__toolbar">
        <div className="balanced-mind-map__view-controls" aria-label="节点显示范围">
          <button type="button" className={!rootCollapsed && expanded.size === 0 ? 'is-active' : ''} onClick={() => showNodes([])}>概览</button>
          <button type="button" className={!rootCollapsed && expanded.size === allExpandable.length && allExpandable.length ? 'is-active' : ''} disabled={!allExpandable.length} onClick={() => showNodes(allExpandable)}>展开全部</button>
        </div>
        <span className="balanced-mind-map__stats">{children.length} 个主分支 · {nodeCount} 个节点</span>
        <div className="balanced-mind-map__zoom-controls">
          <button type="button" aria-label="缩小" onClick={() => zoomAt(1 / 1.2)}>−</button>
          <span aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" aria-label="放大" onClick={() => zoomAt(1.2)}>+</button>
          {typeof document !== 'undefined' && document.fullscreenEnabled ? <button type="button" onClick={toggleFullscreen}>{fullscreen ? '退出全屏' : '全屏查看'}</button> : null}
          <button type="button" aria-label="复位" className="balanced-mind-map__reset" onClick={reset}>复位</button>
          {onExport ? <button type="button" className="balanced-mind-map__export" onClick={onExport}>导出导图</button> : null}
        </div>
      </header>
      {fullscreenError ? <p role="status">{fullscreenError}</p> : null}
      <p className="balanced-mind-map__hint">点击节点展开或收起 · 拖动画布 · 滚轮缩放</p>
      <div
        className={`balanced-mind-map__viewport${dragging ? ' is-dragging' : ''}`}
        ref={viewportRef}
        tabIndex={0}
        aria-label="思维导图画布，可拖动，滚轮缩放，方向键移动，Home 键查看全景"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onClickCapture={event => {
          if (suppressClickRef.current && event.detail !== 0) {
            event.preventDefault();
            event.stopPropagation();
          }
          suppressClickRef.current = false;
        }}
        onKeyDown={event => {
          if (event.target !== event.currentTarget) return;
          const offset = { ArrowLeft: [-80, 0], ArrowRight: [80, 0], ArrowUp: [0, -80], ArrowDown: [0, 80] }[event.key];
          if (event.key === 'Home') { event.preventDefault(); fit(); }
          else if (offset) { event.preventDefault(); setCamera(current => ({ ...current, x: current.x + offset[0], y: current.y + offset[1] })); }
        }}
      >
        {root ? (
          <div className="balanced-mind-map__stage">
            <div className="balanced-mind-map__scale" style={{ transform: `scale(${zoom})`, left: (layout.viewportWidth - layout.width * zoom) / 2 + camera.x, top: (layout.viewportHeight - layout.height * zoom) / 2 + camera.y }}>
              <div className="balanced-mind-map__diagram" ref={diagramRef} role="tree" aria-label={label}>
                <svg className="balanced-mind-map__links" width={layout.width} height={layout.height} aria-hidden="true">
                  {layout.edges.map((edge, index) => <path key={index} d={edge.path} stroke={edge.color} />)}
                </svg>
                <ol className="balanced-mind-map__side balanced-mind-map__side--left" role="group">
                  {!rootCollapsed && left.map((child, index) => (
                    <Branch key={child.id || `${child.title}-${index}`} node={child} path={`root.${child.id || index}`} index={index} direction="left" depth={2} expanded={expanded} onToggle={toggle} />
                  ))}
                </ol>
                <article
                  className="balanced-mind-map__root"
                  role={children.length ? 'button' : 'treeitem'}
                  tabIndex={children.length ? 0 : undefined}
                  aria-label={children.length ? `${rootCollapsed ? '展开' : '收起'}${root.title || '中心主题'}` : undefined}
                  aria-expanded={children.length ? !rootCollapsed : undefined}
                  onClick={children.length ? () => { setRootCollapsed(value => !value); fit(); } : undefined}
                  onKeyDown={children.length ? event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      if (!event.repeat) { setRootCollapsed(value => !value); fit(); }
                    }
                  } : undefined}
                >
                  <span>中心主题</span>
                  <strong>{root.title || '未命名主题'}</strong>
                  {root.summary ? <small>{root.summary}</small> : null}
                </article>
                <ol className="balanced-mind-map__side balanced-mind-map__side--right" role="group">
                  {!rootCollapsed && right.map((child, offset) => {
                    const index = middle + offset;
                    return <Branch key={child.id || `${child.title}-${index}`} node={child} path={`root.${child.id || index}`} index={index} direction="right" depth={2} expanded={expanded} onToggle={toggle} />;
                  })}
                </ol>
              </div>
            </div>
          </div>
        ) : <p className="resource-preview-empty">当前思维导图暂无节点。</p>}
      </div>
    </section>
  );
}
