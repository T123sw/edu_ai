import { useEffect, useState } from 'react';
import { TreeSelect } from 'antd';
import { getKnowledgeGraph } from '../../services/teacher/api';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';
import { getWorkspaceTopicOptions, getWorkspaceTopicTree, getWorkspaceTopicAncestors, type WorkspaceTopicNode, type WorkspaceTopicOption } from './workspaceTopicOptions';
import './WorkspaceContextBar.css';

export function WorkspaceContextBar({ courseId, courseTitle, scope, onChange }: {
  courseId?: string;
  courseTitle: string;
  scope: WorkspaceScope;
  onChange: (scope: WorkspaceScope) => void;
}) {
  const [options, setOptions] = useState<WorkspaceTopicOption[]>([]);
  const [tree, setTree] = useState<WorkspaceTopicNode[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setOptions([]);
    setTree([]);
    setExpandedKeys([]);
    setError('');
    setLoading(Boolean(courseId));
    if (!courseId) return;
    getKnowledgeGraph(courseId).then((graph) => {
      if (active) {
        setOptions(getWorkspaceTopicOptions(graph.root));
        setTree(getWorkspaceTopicTree(graph.root));
      }
    }).catch(() => {
      if (active) setError('知识点加载失败，请刷新重试');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [courseId]);
  useEffect(() => {
    setExpandedKeys([...new Set([...tree.map(node => node.value), ...getWorkspaceTopicAncestors(tree, scope.scopeId)])]);
  }, [tree, scope.scopeId]);
  const current = options.find((option) => option.value === scope.scopeId);
  return <div className="workspace-context-bar" data-testid="workspace-context-bar">
    <span className="workspace-context-bar__label">讨论主题</span>
    <TreeSelect
      aria-label="选择讨论知识点"
      title={current?.title || courseTitle}
      showSearch
      filterTreeNode={(input, node) => String(node.path || node.title || '').toLocaleLowerCase().includes(input.toLocaleLowerCase())}
      loading={loading}
      disabled={!courseId}
      placeholder={courseId ? '选择知识点' : '请先选择课程'}
      className="workspace-context-bar__select"
      value={current?.value}
      treeData={tree}
      treeLine
      treeExpandAction="click"
      treeExpandedKeys={expandedKeys}
      onTreeExpand={(keys) => setExpandedKeys(keys.map(String))}
      treeNodeLabelProp="title"
      popupMatchSelectWidth={360}
      classNames={{ popup: { root: 'workspace-topic-tree-popup' } }}
      notFoundContent={loading ? '正在加载知识点…' : error || '暂无匹配的知识点'}
      onChange={(value) => onChange({ scopeType: 'knowledge_point', scopeId: value, scopeLabel: options.find((option) => option.value === value)?.title })}
    />
    {error && <span className="workspace-context-bar__error" role="alert">{error}</span>}
  </div>;
}
