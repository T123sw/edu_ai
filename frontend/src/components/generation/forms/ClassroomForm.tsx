import type { ClassroomConfig } from "../definitions/classroom";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

export function ClassroomForm({ value, onChange, errors = {} }: GenerationFormProps<ClassroomConfig>) {
  const patch = (next: Partial<ClassroomConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="classroom">
    <p className="generation-form-note">按教学需求生成视频，未指定时以约 5 分钟为目标。</p>
    <GenerationField label="研究主题" required error={errors.topic}><textarea autoFocus placeholder="例如：冒泡排序为什么能把最大值逐步移动到末尾？" value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
    <GenerationField label="配音"><select value={value.voiceEnabled === undefined ? "auto" : value.voiceEnabled ? "on" : "off"} onChange={(event) => patch({ voiceEnabled: event.target.value === "auto" ? undefined : event.target.value === "on" })}><option value="auto">按需求安排</option><option value="on">需要配音</option><option value="off">不需要配音</option></select></GenerationField><GenerationField label="视频目标时长（分钟）"><input type="number" min="0.1" step="0.5" placeholder="默认约 5 分钟" value={value.durationMinutes ?? ""} onChange={event => patch({ durationMinutes: event.target.value ? Number(event.target.value) : undefined })} /></GenerationField><GenerationField label="补充要求"><textarea value={value.specialRequirements} onChange={(event) => patch({ specialRequirements: event.target.value })} /></GenerationField>
  </div>;
}
