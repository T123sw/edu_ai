import { useEffect, useRef } from "react";

import type { KnowledgeBaseDocument } from "../../stitch/api/types";
import { MaterialIcon } from "../../stitch/shared";
import {
  GenerationSourceSelector,
  generationSourceSummary,
  type GenerationSourceSelection,
} from "./GenerationSourceSelector";
import type { GenerationRegistryItem } from "./generationRegistry";

export function GenerationPromptDialog({
  resource,
  value,
  source,
  documents,
  error,
  queued,
  onValueChange,
  onSourceChange,
  onClose,
  onSubmit,
}: {
  resource: GenerationRegistryItem;
  value: string;
  source: GenerationSourceSelection;
  documents: KnowledgeBaseDocument[];
  error?: string | null;
  queued?: boolean;
  onValueChange: (value: string) => void;
  onSourceChange: (source: GenerationSourceSelection) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const dialogRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [resource.resourceType]);

  return (
    <div
      className="generation-factory__modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        ref={dialogRef}
        className="generation-factory__modal generation-factory__prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="generation-prompt-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
          if (event.key !== "Tab") return;
          const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
          ) || []).filter((element) => element.getClientRects().length > 0);
          if (focusable.length === 0) return;
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }}
      >
        <header>
          <div><span>交给 Agent</span><h2 id="generation-prompt-title">创建{resource.label}</h2></div>
          <button type="button" aria-label="关闭" onClick={onClose}><MaterialIcon name="close" /></button>
        </header>
        <form onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
          <div className="generation-factory__modal-body">
            <label className="generation-factory__prompt-field">
              <span>描述你想生成的内容</span>
              <textarea
                ref={inputRef}
                value={value}
                rows={6}
                placeholder={resource.placeholder}
                aria-describedby="generation-prompt-help"
                onChange={(event) => onValueChange(event.target.value)}
              />
            </label>
            <p id="generation-prompt-help" className="generation-factory__prompt-help">
              Agent 会从你的描述中提取受众、数量、难度、风格和结构等要求。
            </p>
            <details className="generation-factory__source-details">
              <summary>资料范围：{generationSourceSummary(source)}</summary>
              <GenerationSourceSelector documents={documents} value={source} onChange={onSourceChange} />
            </details>
            {error ? <p className="generation-factory__error" role="alert">{error}</p> : null}
          </div>
          <footer>
            <button type="button" onClick={onClose}>取消</button>
            <button type="submit" className="is-primary" disabled={!value.trim() || queued}>
              {queued ? "已有请求等待发送" : "交给 AI"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
