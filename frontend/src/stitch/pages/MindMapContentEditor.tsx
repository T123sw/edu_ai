import type { EditableMindMapNode } from "./mindMapEditing";
import {
  addMindMapChild,
  removeMindMapNode,
  updateMindMapNodeTitle,
} from "./mindMapEditing";

type Props = {
  root: EditableMindMapNode;
  onChange: (root: EditableMindMapNode) => void;
};

export function MindMapContentEditor({ root, onChange }: Props) {
  const renderNode = (node: EditableMindMapNode, depth: number) => (
    <div key={node.id} className="mt-2">
      <div className="flex items-center gap-2" style={{ paddingLeft: `${depth * 20}px` }}>
        <input
          aria-label={`节点 ${node.id}`}
          value={node.title}
          onChange={(event) => onChange(updateMindMapNodeTitle(root, node.id, event.target.value))}
          className="min-w-0 flex-1 rounded-xl border border-(--shell-border) bg-white px-3 py-2 text-sm font-semibold outline-hidden focus:border-(--accent-border)"
        />
        <button type="button" onClick={() => onChange(addMindMapChild(root, node.id))} className="rounded-full border border-(--shell-border) px-3 py-2 text-xs font-bold">
          添加子节点
        </button>
        {node.id !== root.id ? (
          <button type="button" onClick={() => onChange(removeMindMapNode(root, node.id))} className="rounded-full border border-rose-200 px-3 py-2 text-xs font-bold text-rose-600">
            删除
          </button>
        ) : null}
      </div>
      {node.children.map((child) => renderNode(child, depth + 1))}
    </div>
  );

  return <div className="mt-4 rounded-2xl bg-(--surface-subtle) p-3">{renderNode(root, 0)}</div>;
}
