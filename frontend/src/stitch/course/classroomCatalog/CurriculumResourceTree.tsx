import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import type { ClassroomCatalogResource } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { catalogLeafSummary, catalogResourceLabel, catalogResourceStatus, type CurriculumTreeNode } from "./catalogPresentation";

type Props = {
  nodes: CurriculumTreeNode[];
  selectedNodeId: string | null;
  selectedResourceId: string | null;
  openKeys: ReadonlySet<string>;
  onToggle: (key: string) => void;
  onSelectNode: (nodeId: string) => void;
  onSelectResource: (nodeId: string, resourceId: string) => void;
};

type Item = {
  key: string;
  kind: "branch" | "leaf" | "resource";
  title: string;
  depth: number;
  parentKey: string | null;
  node?: CurriculumTreeNode;
  nodeId?: string;
  resource?: ClassroomCatalogResource;
};

const resourceIcon = (resource: ClassroomCatalogResource) =>
  resource.standard_kind === "classroom" ? "play_circle" : resource.standard_kind === "practice" ? "quiz" : "description";

function flatten(nodes: CurriculumTreeNode[], openKeys: ReadonlySet<string>): Item[] {
  const result: Item[] = [];
  const visit = (entries: CurriculumTreeNode[], depth: number, parentKey: string | null) => {
    entries.forEach((node) => {
      const nodeId = node.leaf?.leaf_id;
      result.push({ key: node.key, kind: node.kind, title: node.title, depth, parentKey, node, nodeId });
      if (!openKeys.has(node.key)) return;
      if (node.kind === "branch") visit(node.children, depth + 1, node.key);
      else node.leaf?.resources.forEach((resource) => result.push({
        key: `resource:${node.leaf!.leaf_id}:${resource.material_id}`,
        kind: "resource",
        title: catalogResourceLabel(resource),
        depth: depth + 1,
        parentKey: node.key,
        nodeId: node.leaf!.leaf_id,
        resource,
      }));
    });
  };
  visit(nodes, 1, null);
  return result;
}

export function CurriculumResourceTree({ nodes, selectedNodeId, selectedResourceId, openKeys, onToggle, onSelectNode, onSelectResource }: Props) {
  const items = useMemo(() => flatten(nodes, openKeys), [nodes, openKeys]);
  const selectedKey = selectedResourceId && selectedNodeId
    ? `resource:${selectedNodeId}:${selectedResourceId}`
    : selectedNodeId ? `leaf:${selectedNodeId}` : null;
  const [focusedKey, setFocusedKey] = useState<string | null>(selectedKey);
  const refs = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    if (selectedKey && items.some((item) => item.key === selectedKey)) setFocusedKey(selectedKey);
    else if (!items.some((item) => item.key === focusedKey)) setFocusedKey(items[0]?.key ?? null);
  }, [focusedKey, items, selectedKey]);

  const focusItem = (key?: string) => {
    if (!key) return;
    setFocusedKey(key);
    requestAnimationFrame(() => refs.current.get(key)?.focus());
  };
  const activate = (item: Item) => {
    if (item.kind === "branch") onToggle(item.key);
    else if (item.kind === "leaf" && item.nodeId) onSelectNode(item.nodeId);
    else if (item.resource && item.nodeId) onSelectResource(item.nodeId, item.resource.material_id);
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, item: Item) => {
    const index = items.findIndex((candidate) => candidate.key === item.key);
    if (event.key === "ArrowUp") focusItem(items[Math.max(0, index - 1)]?.key);
    else if (event.key === "ArrowDown") focusItem(items[Math.min(items.length - 1, index + 1)]?.key);
    else if (event.key === "Home") focusItem(items[0]?.key);
    else if (event.key === "End") focusItem(items.at(-1)?.key);
    else if (event.key === "ArrowRight" && item.kind !== "resource") {
      if (!openKeys.has(item.key)) onToggle(item.key); else focusItem(items[index + 1]?.key);
    } else if (event.key === "ArrowLeft") {
      if (item.kind !== "resource" && openKeys.has(item.key)) onToggle(item.key); else focusItem(item.parentKey ?? undefined);
    } else if (event.key === "Enter" || event.key === " ") activate(item);
    else return;
    event.preventDefault();
  };

  return <ul className="curriculum-resource-tree" role="tree" aria-label="课程目录">
    {items.map((item) => {
      const expandable = item.kind !== "resource";
      const selected = item.kind === "resource"
        ? item.nodeId === selectedNodeId && item.resource?.material_id === selectedResourceId
        : item.kind === "leaf" && item.nodeId === selectedNodeId && !selectedResourceId;
      return <li key={item.key} role="treeitem" aria-level={item.depth} aria-expanded={expandable ? openKeys.has(item.key) : undefined} aria-selected={selected}
        className={`curriculum-resource-tree__item is-${item.kind}${selected ? " is-selected" : ""}`}
        style={{ "--tree-depth": item.depth } as CSSProperties}>
        <button ref={(element) => { if (element) refs.current.set(item.key, element); else refs.current.delete(item.key); }} type="button"
          tabIndex={focusedKey === item.key ? 0 : -1} onFocus={() => setFocusedKey(item.key)} onKeyDown={(event) => handleKeyDown(event, item)}
          onClick={() => { setFocusedKey(item.key); activate(item); if (item.kind === "leaf" && !openKeys.has(item.key)) onToggle(item.key); }}>
          {expandable
            ? <MaterialIcon name={openKeys.has(item.key) ? "expand_more" : "chevron_right"} className="curriculum-resource-tree__chevron" />
            : <MaterialIcon name={resourceIcon(item.resource!)} className="curriculum-resource-tree__resource-icon" />}
          <span className="curriculum-resource-tree__label"><strong>{item.title}</strong>
            {item.kind === "leaf" && item.node?.leaf ? <small>{catalogLeafSummary(item.node.leaf)}</small> : null}
          </span>
          {item.resource ? <span className={`catalog-status is-${item.resource.progress?.status || item.resource.review_status}`}>{catalogResourceStatus(item.resource)}</span> : null}
        </button>
      </li>;
    })}
  </ul>;
}
