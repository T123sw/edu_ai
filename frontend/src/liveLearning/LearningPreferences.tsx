import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
type Preference = { memory_id: string; revision: string; value: string; course_id: string | null };
const names: Record<string, string> = { language: '语言', response_detail: '讲解详略', learning_goal: '学习目标', resource_preference: '资料偏好', learning_style: '学习方式' };
export function LearningPreferences() {
  const [preferences, setPreferences] = useState<Record<string, Preference>>({});
  const [error, setError] = useState('');
  const refresh = async () => { const result = await apiRequest<{ preferences: Record<string, Preference> }>('/api/agent-memory/preferences'); setPreferences(result.preferences); };
  useEffect(() => { void refresh().catch(e => setError(e.message)); }, []);
  const change = async (item: Preference, value?: string) => {
    setError('');
    try { await apiRequest(`/api/agent-memory/items/${encodeURIComponent(item.memory_id)}${value === undefined ? '?expected_revision=' + item.revision : ''}`, value === undefined ? { method: 'DELETE' } : { method: 'PUT', body: JSON.stringify({ value, expected_revision: item.revision }) }); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
  };
  return <section aria-label="学习偏好" style={{ maxWidth: 900, margin: '24px auto', padding: 24 }}><h2>学习偏好</h2><p>本次提问中的要求优先。删除后，这条偏好不再用于后续准备和答疑。</p>
    {error && <p role="alert">{error}</p>}{Object.entries(preferences).map(([axis, item]) => <PreferenceEditor key={item.memory_id + item.revision} label={names[axis] || axis} item={item} onSave={value => void change(item, value)} onDelete={() => void change(item)} />)}
    {!Object.keys(preferences).length && !error && <p>暂无已记录的全局学习偏好。</p>}
  </section>;
}
function PreferenceEditor({ label, item, onSave, onDelete }: { label: string; item: Preference; onSave: (value: string) => void; onDelete: () => void }) {
  const [value, setValue] = useState(item.value);
  return <div style={{ marginBottom: 16 }}><label>{label}<input value={value} maxLength={2000} onChange={e => setValue(e.target.value)} /></label><button disabled={!value.trim()} onClick={() => onSave(value)}>保存更正</button><button onClick={onDelete}>删除偏好</button></div>;
}
