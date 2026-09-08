import { useEffect, useState } from 'react';
import { Popover, TreeSelect } from 'antd';
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
  const [adjusting, setAdjusting] = useState(false);
  useEffect(() => {
    let active = true;
    setAdjusting(false);
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
  const label = scope.scopeType === 'course' ? '课程整体' : current?.label || scope.scopeLabel || '当前知识点';
  const changeScope = (next: WorkspaceScope) => { onChange(next); setAdjusting(false); };
  return <div className="workspace-context-bar" data-testid="workspace-context-bar">
    <span className="workspace-context-bar__label">当前讨论范围</span>
    <strong className="workspace-context-bar__current" title={current?.title || courseTitle}>{label}</strong>
    <Popover trigger="click" placement="bottomLeft" open={adjusting} onOpenChange={setAdjusting}
      content={<div className="workspace-context-bar__adjustment">
        <button type="button" className="workspace-context-bar__course" onClick={() => changeScope({ scopeType: 'course' })}>课程整体</button>
        <TreeSelect
          aria-label="选择备课知识点"
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
          getPopupContainer={(trigger) => trigger.parentElement!}
          popupMatchSelectWidth={360}
          classNames={{ popup: { root: 'workspace-topic-tree-popup' } }}
          notFoundContent={loading ? '正在加载知识点…' : error || '暂无匹配的知识点'}
          onChange={(value) => changeScope({ scopeType: 'knowledge_point', scopeId: value, scopeLabel: options.find((option) => option.value === value)?.label })}
        />
        {error && <span className="workspace-context-bar__error" role="alert">{error}</span>}
      </div>}>
      <button type="button" className="workspace-context-bar__adjust" disabled={!courseId} aria-expanded={adjusting}>调整</button>
    </Popover>
  </div>;
}
