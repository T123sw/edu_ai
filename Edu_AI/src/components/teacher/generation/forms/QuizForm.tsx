import type { QuizConfig, QuizQuestionType } from "../definitions/quiz";
import type { GenerationFormProps } from "../definitions/types";
import { GenerationField } from "./formFields";

const types: Array<[QuizQuestionType, string]> = [["choice", "选择题"], ["blank", "填空题"], ["short", "简答题"], ["judge", "判断题"]];

export function QuizForm({ value, onChange, errors = {} }: GenerationFormProps<QuizConfig>) {
  const patch = (next: Partial<QuizConfig>) => onChange({ ...value, ...next });
  const toggleType = (type: QuizQuestionType) => patch({ questionTypes: value.questionTypes.includes(type) ? value.questionTypes.filter((item) => item !== type) : [...value.questionTypes, type] });
  return <div className="generation-factory__form" data-resource-form="quiz">
    <GenerationField label="习题主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} /></GenerationField>
    <GenerationField label="适用对象"><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField>
    <GenerationField label="难度"><select value={value.difficulty} onChange={(event) => patch({ difficulty: event.target.value as QuizConfig["difficulty"] })}><option value="easy">基础</option><option value="medium">中等</option><option value="hard">挑战</option></select></GenerationField>
    <GenerationField label="题目数量" required error={errors.count}><input type="number" min={1} max={50} value={value.count} onChange={(event) => patch({ count: Number(event.target.value) })} /></GenerationField>
    <fieldset><legend>题型</legend><div className="generation-choice-grid">{types.map(([type, label]) => <label key={type}><input type="checkbox" checked={value.questionTypes.includes(type)} onChange={() => toggleType(type)} />{label}</label>)}</div>{errors.questionTypes ? <small role="alert">{errors.questionTypes}</small> : null}</fieldset>
    <div className="generation-choice-grid"><label><input type="checkbox" checked={value.includeAnswers} onChange={(event) => patch({ includeAnswers: event.target.checked })} />附带答案</label><label><input type="checkbox" checked={value.includeExplanations} onChange={(event) => patch({ includeExplanations: event.target.checked })} />附带解析</label></div>
  </div>;
}
