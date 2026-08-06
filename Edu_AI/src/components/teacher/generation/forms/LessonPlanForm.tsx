import type { LessonPlanConfig } from "../definitions/lessonPlan";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField, lines } from "./formFields";

export function LessonPlanForm({ value, onChange, errors = {} }: GenerationFormProps<LessonPlanConfig>) {
  const patch = (next: Partial<LessonPlanConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="lesson_plan">
    <fieldset><legend>基本信息</legend><GenerationField label="教学主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} placeholder="例如：牛顿第二定律" /></GenerationField><GenerationField label="年级 / 适用对象" required error={errors.audience}><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField><GenerationField label="课时（分钟）" required error={errors.durationMinutes}><input type="number" min={10} max={480} value={value.durationMinutes} onChange={(event) => patch({ durationMinutes: Number(event.target.value) })} /></GenerationField><GenerationField label="课型"><select value={value.lessonType} onChange={(event) => patch({ lessonType: event.target.value as LessonPlanConfig["lessonType"] })}><option value="new_lesson">新授课</option><option value="review_lesson">复习课</option><option value="inquiry_lesson">探究课</option><option value="practice_lesson">练习课</option></select></GenerationField></fieldset>
    <fieldset><legend>教学目标</legend><GenerationField label="每行一个目标（根据资料建议，可编辑）" required error={errors.objectives}><textarea value={value.objectives.join("\n")} onChange={(event) => patch({ objectives: lines(event.target.value) })} /></GenerationField></fieldset>
    <fieldset><legend>教学过程</legend><GenerationField label="过程安排"><textarea value={value.teachingProcess} onChange={(event) => patch({ teachingProcess: event.target.value })} /></GenerationField></fieldset>
    <fieldset><legend>补充要求</legend><GenerationField label="其他要求"><textarea value={value.specialRequirements} onChange={(event) => patch({ specialRequirements: event.target.value })} /></GenerationField><label className="generation-inline-check"><input type="checkbox" checked={value.outlinePreview} onChange={(event) => patch({ outlinePreview: event.target.checked })} />先生成可确认的教案大纲</label></fieldset>
  </div>;
}
