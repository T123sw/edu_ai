import type { FlashcardConfig } from "../definitions/flashcard";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

export function FlashcardForm({ value, onChange, errors = {} }: GenerationFormProps<FlashcardConfig>) {
  const patch = (next: Partial<FlashcardConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="flashcard">
    <GenerationField label="闪卡标题" required error={errors.title}><input value={value.title} onChange={(event) => patch({ title: event.target.value })} placeholder="纯文本标题" /></GenerationField>
    <GenerationField label="卡片数量" required error={errors.count}><input type="number" min={3} max={30} value={value.count} onChange={(event) => patch({ count: Number(event.target.value) })} /></GenerationField>
    <GenerationField label="难度"><select value={value.difficulty} onChange={(event) => patch({ difficulty: event.target.value as FlashcardConfig["difficulty"] })}><option value="easy">基础</option><option value="medium">中等</option><option value="hard">挑战</option></select></GenerationField>
    <details><summary>更多设置</summary><GenerationField label="分类"><input value={value.category} onChange={(event) => patch({ category: event.target.value })} /></GenerationField><label className="generation-inline-check"><input type="checkbox" checked={value.showSource} onChange={(event) => patch({ showSource: event.target.checked })} />卡片中显示资料来源</label></details>
  </div>;
}
