import { useMemo, useState } from "react";

import { updateCourseMaterialContent } from "../api/courses";
import type { CourseMaterial } from "../api/types";
import {
  editableMaterialDraft,
  isTextMaterial,
  parseEditableMaterialDraft,
} from "./materialContentEditing";
import { MindMapContentEditor } from "./MindMapContentEditor";
import type { EditableMindMapNode } from "./mindMapEditing";

type Props = {
  courseId: string;
  material: CourseMaterial;
  onCancel: () => void;
  onSaved: (material: CourseMaterial) => void;
};

export function MaterialContentEditor({ courseId, material, onCancel, onSaved }: Props) {
  const initialDraft = useMemo(() => editableMaterialDraft(material), [material]);
  const [draft, setDraft] = useState(initialDraft);
  const [mindMapRoot, setMindMapRoot] = useState<EditableMindMapNode | null>(() => {
    if (material.material_type !== "graph") return null;
    try {
      const parsed = JSON.parse(initialDraft) as { root?: EditableMindMapNode };
      return parsed.root ?? null;
    } catch {
      return null;
    }
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const textMode = isTextMaterial(material);

  const save = async () => {
    setError("");
    try {
      const content = mindMapRoot
        ? { root: mindMapRoot }
        : parseEditableMaterialDraft(material, draft);
      setSaving(true);
      const updated = await updateCourseMaterialContent(
        courseId,
        material.material_type,
        material.material_id,
        content,
      );
      onSaved(updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-3xl border border-(--shell-border) bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-black text-(--app-text)">编辑资源内容</h3>
          <p className="mt-1 text-sm text-(--muted-text)">
            {textMode ? "支持 Markdown；保存后预览立即更新。" : "结构化资源使用 JSON 编辑，保存前会自动校验。"}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onCancel} className="rounded-full border border-(--shell-border) px-4 py-2 text-sm font-bold">
            取消
          </button>
          <button type="button" disabled={saving} onClick={() => void save()} className="rounded-full bg-(--accent) px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
            {saving ? "保存中…" : "保存内容"}
          </button>
        </div>
      </div>
      {error ? <p className="mt-3 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">{error}</p> : null}
      {mindMapRoot ? (
        <MindMapContentEditor root={mindMapRoot} onChange={setMindMapRoot} />
      ) : (
        <textarea
          aria-label="资源内容"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          spellCheck={false}
          className="mt-4 min-h-[430px] w-full resize-y rounded-2xl border border-(--shell-border) bg-(--surface-subtle) p-4 font-mono text-sm leading-6 outline-hidden focus:border-(--accent-border)"
        />
      )}
    </section>
  );
}
