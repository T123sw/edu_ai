import type { PptConfig } from "../definitions/ppt";
import type { GenerationFormProps } from "../definitions/types";
import { PptOutlineEditor } from "../previews/PptOutlineEditor";
import { GenerationField } from "./formFields";

export function PptForm({ value, onChange, errors = {} }: GenerationFormProps<PptConfig>) {
  const patch = (next: Partial<PptConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="ppt">
    <GenerationField label="PPT 标题" required error={errors.deckTitle}><input value={value.deckTitle} onChange={(event) => patch({ deckTitle: event.target.value })} /></GenerationField>
    <GenerationField label="副标题"><input value={value.deckSubtitle} onChange={(event) => patch({ deckSubtitle: event.target.value })} /></GenerationField>
    <GenerationField label="适用对象"><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField>
    <GenerationField label="演示目标"><textarea value={value.objective} onChange={(event) => patch({ objective: event.target.value })} /></GenerationField>
    <GenerationField label="目标页数" required error={errors.slideCount}><input type="number" min={5} max={30} value={value.slideCount} onChange={(event) => patch({ slideCount: Number(event.target.value) })} /></GenerationField>
    <GenerationField label="内容重点"><input value={value.focus} onChange={(event) => patch({ focus: event.target.value })} /></GenerationField>
    <GenerationField label="视觉风格"><input value={value.style} onChange={(event) => patch({ style: event.target.value })} /></GenerationField>
    <fieldset><legend>版式模板</legend><div className="ppt-template-grid"><button type="button" aria-pressed={value.template === "heu_academic_elegant"} onClick={() => patch({ template: "heu_academic_elegant" })}><span className="ppt-template-thumb is-elegant" /><strong>学术雅致</strong></button><button type="button" aria-pressed={value.template === "heu_academic_basic"} onClick={() => patch({ template: "heu_academic_basic" })}><span className="ppt-template-thumb is-basic" /><strong>学术简洁</strong></button></div></fieldset>
    <PptOutlineEditor value={value.outline} onChange={(outline) => patch({ outline })} error={errors.outline} />
  </div>;
}
