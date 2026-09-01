import type { MindMapConfig } from "../definitions/mindMap";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

export function MindMapForm({ value, onChange, errors = {} }: GenerationFormProps<MindMapConfig>) {
  const patch = (next: Partial<MindMapConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="mind_map">
    <GenerationField label="思维导图主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
    <GenerationField label="层级深度" error={errors.depth}><input type="number" min={2} max={5} value={value.depth} onChange={(event) => patch({ depth: Number(event.target.value) })} /></GenerationField>
    <details><summary>更多设置</summary><GenerationField label="关系侧重点"><textarea value={value.description} onChange={(event) => patch({ description: event.target.value })} /></GenerationField></details>
    <p className="generation-form-note">生成结果会保存为课程资源中的“思维导图”，不会写入或改动课程知识结构。</p>
  </div>;
}
