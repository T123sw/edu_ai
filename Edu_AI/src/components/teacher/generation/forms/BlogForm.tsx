import type { BlogConfig } from "../definitions/blog";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

export function BlogForm({ value, onChange, errors = {} }: GenerationFormProps<BlogConfig>) {
  const patch = (next: Partial<BlogConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="blog">
    <GenerationField label="博客主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} placeholder="例如：用生活例子理解量子隧穿" /></GenerationField>
    <GenerationField label="目标读者"><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField>
    <GenerationField label="表达语气"><select value={value.tone} onChange={(event) => patch({ tone: event.target.value as BlogConfig["tone"] })}><option value="academic">学术严谨</option><option value="popular">通俗易懂</option><option value="narrative">叙事讲解</option></select></GenerationField>
    <GenerationField label="文章长度"><select value={value.length} onChange={(event) => patch({ length: event.target.value as BlogConfig["length"] })}><option value="short">短文</option><option value="medium">中等</option><option value="long">长文</option></select></GenerationField>
    <label className="generation-inline-check"><input type="checkbox" checked={value.includeVisuals} onChange={(event) => patch({ includeVisuals: event.target.checked })} />自动规划并检索合适配图</label>
    <details><summary>更多设置</summary><GenerationField label="文章结构"><input value={value.structure} onChange={(event) => patch({ structure: event.target.value })} /></GenerationField><GenerationField label="补充要求"><textarea value={value.specialRequirements} onChange={(event) => patch({ specialRequirements: event.target.value })} /></GenerationField></details>
  </div>;
}
