import type { GenerationFormProps } from '../components/generation/definitions/types';
import { GenerationField } from '../components/generation/forms/formFields';
type Config = Record<string, unknown>;

export function PodcastForm({ value, onChange, errors = {} }: GenerationFormProps<Config>) {
  return <div className="generation-factory__form">
    <GenerationField label="播客主题" required error={errors.topic}><input value={String(value.topic || '')} onChange={e => onChange({ ...value, topic: e.target.value })} /></GenerationField>
    <GenerationField label="目标时长"><select value={Number(value.duration_minutes)} onChange={e => onChange({ ...value, duration_minutes: Number(e.target.value) })}><option value={3}>约 3 分钟</option><option value={5}>约 5 分钟</option><option value={8}>约 8 分钟</option></select></GenerationField>
    <GenerationField label="讲解重点"><textarea value={String(value.focus || '')} onChange={e => onChange({ ...value, focus: e.target.value })} maxLength={2000} placeholder="例如：用生活中的例子解释原理" /></GenerationField>
    <p className="generation-form-note">生成分章节的音频讲解与文字稿，实际时长会随内容和语速变化。</p>
  </div>;
}

export function ScenarioForm({ value, onChange, errors = {} }: GenerationFormProps<Config>) {
  return <div className="generation-factory__form">
    <GenerationField label="案例主题" required error={errors.topic}><input value={String(value.topic || '')} onChange={e => onChange({ ...value, topic: e.target.value })} /></GenerationField>
    <GenerationField label="难度"><select value={String(value.difficulty)} onChange={e => onChange({ ...value, difficulty: e.target.value })}><option value="easy">基础</option><option value="medium">中等</option><option value="hard">挑战</option></select></GenerationField>
    <GenerationField label="情景设定"><textarea value={String(value.setting || '')} onChange={e => onChange({ ...value, setting: e.target.value })} maxLength={2000} placeholder="例如：你负责排查一个响应缓慢的网站" /></GenerationField>
    <p className="generation-form-note">进入模拟情景，选择处理方式，查看不同后果与复盘。</p>
  </div>;
}
