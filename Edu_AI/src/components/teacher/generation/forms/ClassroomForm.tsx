import type { ClassroomConfig } from "../definitions/classroom";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

export function ClassroomForm({ value, onChange, errors = {} }: GenerationFormProps<ClassroomConfig>) {
  const patch = (next: Partial<ClassroomConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="classroom">
    <p className="generation-form-note">只需告诉我们本节课要研究什么，其余课堂结构会自动完成。</p>
    <GenerationField label="研究主题" required error={errors.topic}><textarea autoFocus placeholder="例如：冒泡排序为什么能把最大值逐步移动到末尾？" value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
  </div>;
}
