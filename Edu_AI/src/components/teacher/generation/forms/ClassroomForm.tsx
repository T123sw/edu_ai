import type { ClassroomConfig } from "../definitions/classroom";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField, lines } from "./formFields";

export function ClassroomForm({ value, onChange, errors = {} }: GenerationFormProps<ClassroomConfig>) {
  const patch = (next: Partial<ClassroomConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="classroom">
    <GenerationField label="课堂主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
    <GenerationField label="适用对象"><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField>
    <GenerationField label="课堂目标（每行一个）" required error={errors.objectives}><textarea value={value.objectives.join("\n")} onChange={(event) => patch({ objectives: lines(event.target.value) })} /></GenerationField>
    <GenerationField label="场景数量" required error={errors.sceneCount}><input type="number" min={1} max={30} value={value.sceneCount} onChange={(event) => patch({ sceneCount: Number(event.target.value) })} /></GenerationField>
    <GenerationField label="预计时长（分钟）" required error={errors.durationMinutes}><input type="number" min={5} max={180} value={value.durationMinutes} onChange={(event) => patch({ durationMinutes: Number(event.target.value) })} /></GenerationField>
    <GenerationField label="教学方式"><select value={value.teachingStyle} onChange={(event) => patch({ teachingStyle: event.target.value as ClassroomConfig["teachingStyle"] })}><option value="guided">引导讲解</option><option value="lecture">系统讲授</option><option value="inquiry">问题探究</option></select></GenerationField>
    <label className="generation-inline-check"><input type="checkbox" checked={value.voiceEnabled} onChange={(event) => patch({ voiceEnabled: event.target.checked })} />生成课堂配音</label>
    {value.voiceEnabled ? <GenerationField label="配音音色"><select value={value.voice} onChange={(event) => patch({ voice: event.target.value as ClassroomConfig["voice"] })}><option value="alloy">沉稳中性</option><option value="nova">清晰明快</option><option value="shimmer">温和自然</option></select></GenerationField> : null}
    <GenerationField label="补充要求"><textarea value={value.specialRequirements} onChange={(event) => patch({ specialRequirements: event.target.value })} /></GenerationField>
  </div>;
}
