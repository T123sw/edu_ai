import type { GenerationFormProps } from "../definitions/types";
import type { ReportConfig } from "../definitions/report";
import { GenerationField } from "./formFields";

export function ReportForm({ value, onChange, errors = {} }: GenerationFormProps<ReportConfig>) {
  const patch = (next: Partial<ReportConfig>) => onChange({ ...value, ...next });
  return <div className="generation-factory__form" data-resource-form="report">
    <GenerationField label="报告模板" required><select value={value.template} onChange={(event) => patch({ template: event.target.value as ReportConfig["template"] })}><option value="brief">简要报告</option><option value="detailed">详细报告</option><option value="study_plan">学习计划</option><option value="custom">自定义</option></select></GenerationField>
    <GenerationField label="报告主题" required error={errors.topic}><input value={value.topic} onChange={(event) => patch({ topic: event.target.value })} placeholder="例如：本学期力学学习情况分析" /></GenerationField>
    <GenerationField label="适用对象" required error={errors.audience}><input value={value.audience} onChange={(event) => patch({ audience: event.target.value })} /></GenerationField>
    <GenerationField label="分析深度"><select value={value.depth} onChange={(event) => patch({ depth: event.target.value as ReportConfig["depth"] })}><option value="overview">概览</option><option value="standard">标准</option><option value="deep">深入</option></select></GenerationField>
    <GenerationField label="结构重点"><input value={value.structureEmphasis} onChange={(event) => patch({ structureEmphasis: event.target.value })} /></GenerationField>
    <GenerationField label="补充要求"><textarea value={value.specialRequirements} onChange={(event) => patch({ specialRequirements: event.target.value })} /></GenerationField>
    <p className="generation-form-note">资料推荐加载失败时不会清空或阻止上述手动配置。</p>
  </div>;
}
