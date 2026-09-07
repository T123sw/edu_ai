import { useEffect, useState } from 'react';
import { Select } from 'antd';
import { getKnowledgeGraph } from '../../services/teacher/api';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';
import { getWorkspaceTopicOptions, type WorkspaceTopicOption } from './workspaceTopicOptions';
import './WorkspaceContextBar.css';

export function WorkspaceContextBar({ courseId, courseTitle, scope, onChange }: {
  courseId?: string;
  courseTitle: string;
  scope: WorkspaceScope;
  onChange: (scope: WorkspaceScope) => void;
}) {
  const [options, setOptions] = useState<WorkspaceTopicOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setOptions([]);
    setError('');
    setLoading(Boolean(courseId));
    if (!courseId) return;
    getKnowledgeGraph(courseId).then((graph) => {
      if (active) setOptions(getWorkspaceTopicOptions(graph.root));
    }).catch(() => {
      if (active) setError('知识点加载失败，请刷新重试');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [courseId]);
  const current = options.find((option) => option.value === scope.scopeId);
  return <div className="workspace-context-bar" data-testid="workspace-context-bar">
    <span className="workspace-context-bar__label">讨论主题</span>
    <Select
      aria-label="选择讨论知识点"
      title={current?.title || courseTitle}
      showSearch
      filterOption={(input, option) => String(option?.title || option?.label || '').toLocaleLowerCase().includes(input.toLocaleLowerCase())}
      loading={loading}
      disabled={!courseId}
      placeholder={courseId ? '选择知识点' : '请先选择课程'}
      className="workspace-context-bar__select"
      value={current?.value}
      options={options}
      notFoundContent={loading ? '正在加载知识点…' : error || '暂无匹配的知识点'}
      onChange={(value) => onChange({ scopeType: 'knowledge_point', scopeId: value, scopeLabel: options.find((option) => option.value === value)?.title })}
    />
    {error && <span className="workspace-context-bar__error" role="alert">{error}</span>}
  </div>;
}
