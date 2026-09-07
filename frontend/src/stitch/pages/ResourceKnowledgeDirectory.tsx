import { FolderOutlined, FolderOpenOutlined } from "@ant-design/icons";
import { useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import type { CourseMaterial, KnowledgeGraphNode } from "../api/types";
import { courseMaterialKey } from "../api/courseMaterialTarget";
import { getCourseMaterialTypeMeta } from "../api/courseMaterialPresentation";
import { MaterialIcon } from "../shared";
import { buildResourceDirectory, type ResourceDirectoryNode } from "./resourceKnowledgeDirectory";
import "../course/classroomCatalog/curriculumResourceTree.css";

type Props = {
  root: KnowledgeGraphNode | null;
  materials: CourseMaterial[];
  activeKey: string | null;
  searching?: boolean;
  onSelect: (material: CourseMaterial) => void;
};
type Item = { key: string; parentKey?: string; depth: number; node?: ResourceDirectoryNode; material?: CourseMaterial; open?: boolean; containsActive?: boolean };
function containsActive(node: ResourceDirectoryNode, key: string | null): boolean {
  return node.materials.some(item => courseMaterialKey(item.material_type, item.material_id) === key)
    || node.children.some(child => containsActive(child, key));
}

export function ResourceKnowledgeDirectory({ root, materials, activeKey, searching = false, onSelect }: Props) {
  const nodes = useMemo(() => buildResourceDirectory(root, materials), [root, materials]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const items: Item[] = [];
  function visit(entries: ResourceDirectoryNode[], depth = 1, parentKey?: string) {
    entries.forEach(node => {
      if (searching && !node.count) return;
      const key = `node:${node.id}`;
      const active = containsActive(node, activeKey);
      const open = expanded[`${searching ? "search:" : ""}${key}`] ?? (searching || (node.kind === "knowledge" && (depth === 1 || active)));
      items.push({ key, parentKey, depth, node, open, containsActive: active });
      if (!open) return;
      visit(node.children, depth + 1, key);
      node.materials.forEach(material => items.push({
        key: `material:${courseMaterialKey(material.material_type, material.material_id)}`,
        parentKey: key, depth: depth + 1, material,
      }));
    });
  }
  visit(nodes);
  const tabKey = items.some(item => item.key === focusedKey) ? focusedKey : items[0]?.key;
  const toggle = (item: Item) => setExpanded(value => ({ ...value, [`${searching ? "search:" : ""}${item.key}`]: !item.open }));
  const focus = (key?: string) => {
    if (!key) return;
    setFocusedKey(key);
    requestAnimationFrame(() => refs.current.get(key)?.focus());
  };
  const activate = (item: Item) => { if (item.material) onSelect(item.material); else toggle(item); };
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, item: Item, index: number) => {
    if (event.key === "ArrowDown") focus(items[Math.min(items.length - 1, index + 1)]?.key);
    else if (event.key === "ArrowUp") focus(items[Math.max(0, index - 1)]?.key);
    else if (event.key === "Home") focus(items[0]?.key);
    else if (event.key === "End") focus(items.at(-1)?.key);
    else if (event.key === "ArrowRight" && item.node) {
      if (!item.open) toggle(item);
      else if (items[index + 1]?.parentKey === item.key) focus(items[index + 1].key);
    } else if (event.key === "ArrowLeft") {
      if (item.node && item.open) toggle(item); else focus(item.parentKey);
    } else if (event.key === "Enter" || event.key === " ") activate(item);
    else return;
    event.preventDefault();
  };
  return <nav className="resource-directory-scroll" aria-label="按知识点浏览资源">
    <ul className="curriculum-resource-tree" role="tree" aria-label="资源目录">
      {items.map((item, index) => {
        const meta = item.material ? getCourseMaterialTypeMeta(item.material.material_type) : null;
        const title = item.node?.label || item.material?.title || item.material?.topic || "未命名资源";
        const selected = Boolean(item.material && courseMaterialKey(item.material.material_type, item.material.material_id) === activeKey);
        const kind = item.material ? "resource" : item.node?.kind === "collection" ? "collection" : "branch";
        return <li key={item.key} role="treeitem" aria-level={item.depth} aria-selected={selected} aria-expanded={item.node ? item.open : undefined}
          className={`curriculum-resource-tree__item is-${kind}${selected ? " is-selected" : ""}${kind === "collection" && item.containsActive && !item.open ? " is-current-collection" : ""}`}
          style={{ "--tree-depth": item.depth } as CSSProperties}>
          <button type="button" title={title} aria-current={selected ? "page" : undefined}
            ref={element => { if (element) refs.current.set(item.key, element); else refs.current.delete(item.key); }}
            tabIndex={tabKey === item.key ? 0 : -1} onFocus={() => setFocusedKey(item.key)}
            onKeyDown={event => handleKeyDown(event, item, index)} onClick={() => { setFocusedKey(item.key); activate(item); }}>
            <MaterialIcon name={item.node ? item.open ? "expand_more" : "chevron_right" : meta!.icon}
              className={item.node ? "curriculum-resource-tree__chevron" : "curriculum-resource-tree__resource-icon"} />
            {kind === "collection" ? item.open
              ? <FolderOpenOutlined aria-hidden="true" className="curriculum-resource-tree__resource-icon" />
              : <FolderOutlined aria-hidden="true" className="curriculum-resource-tree__resource-icon" /> : null}
            <span className="curriculum-resource-tree__label"><strong>{title}</strong>
              {meta ? <small>{meta.label}{item.material?.is_pinned ? " · 置顶" : ""}</small> : null}
            </span>
            {item.node ? <span className="resource-directory-count">{item.node.count}</span> : null}
          </button>
        </li>;
      })}
    </ul>
  </nav>;
}
