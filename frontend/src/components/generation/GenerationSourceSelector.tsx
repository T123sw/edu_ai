import type { KnowledgeBaseDocument } from "../../stitch/api/types";

export type GenerationSourceMode = "course_auto" | "selected_documents" | "none";
export type GenerationSourceSelection = { mode: GenerationSourceMode; selectedDocumentIds: string[] };

export function initialGenerationSource(selectedDocumentIds: string[]): GenerationSourceSelection {
  const normalized = [...new Set(selectedDocumentIds.map((id) => id.trim()).filter(Boolean))];
  return normalized.length > 0
    ? { mode: "selected_documents", selectedDocumentIds: normalized }
    : { mode: "none", selectedDocumentIds: [] };
}

export function changeSourceMode(selection: GenerationSourceSelection, mode: GenerationSourceMode): GenerationSourceSelection {
  return { mode, selectedDocumentIds: mode === "selected_documents" ? selection.selectedDocumentIds : [] };
}

export function GenerationSourceSelector({ documents, value, onChange }: {
  documents: KnowledgeBaseDocument[];
  value: GenerationSourceSelection;
  onChange: (value: GenerationSourceSelection) => void;
}) {
  const readyCount = documents.filter((document) => document.status === "ready").length;
  const modes: Array<{ id: GenerationSourceMode; title: string; description: string }> = [
    { id: "course_auto", title: "自动使用课程资料", description: `${readyCount} 份资料可检索，系统自动选择相关内容` },
    { id: "selected_documents", title: "仅使用选中文档", description: "明确限定本次生成采用的资料" },
    { id: "none", title: "不使用资料", description: "只根据主题与配置生成，不调用课程资料" },
  ];
  return (
    <fieldset className="generation-source" aria-label="资料范围">
      <legend>确认资料范围</legend>
      <div className="generation-source__modes">
        {modes.map((mode) => (
          <label key={mode.id} className={value.mode === mode.id ? "is-selected" : ""}>
            <input type="radio" name="generation-source-mode" value={mode.id} checked={value.mode === mode.id} onChange={() => onChange(changeSourceMode(value, mode.id))} />
            <span><strong>{mode.title}</strong><small>{mode.description}</small></span>
          </label>
        ))}
      </div>
      {value.mode === "selected_documents" ? (
        <div className="generation-source__documents">
          {documents.length ? documents.map((document) => {
            const ready = document.status === "ready";
            const checked = value.selectedDocumentIds.includes(document.id);
            return (
              <label key={document.id} className={!ready ? "is-disabled" : ""}>
                <input
                  type="checkbox"
                  disabled={!ready}
                  checked={checked}
                  onChange={() => onChange({
                    ...value,
                    selectedDocumentIds: checked
                      ? value.selectedDocumentIds.filter((id) => id !== document.id)
                      : [...value.selectedDocumentIds, document.id],
                  })}
                />
                <span><strong>{document.name}</strong><small>{ready ? `${document.chunk_count} 个检索片段` : document.error_message || `当前状态：${document.status}`}</small></span>
              </label>
            );
          }) : <p>课程中还没有资料。你可以返回课程知识上传，或选择“不使用资料”。</p>}
        </div>
      ) : null}
    </fieldset>
  );
}
