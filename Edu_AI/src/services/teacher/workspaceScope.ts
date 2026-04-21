export type WorkspaceScopeType = 'course' | 'knowledge_point';

export interface WorkspaceScope {
  scopeType: WorkspaceScopeType;
  scopeId?: string;
  scopeLabel?: string;
}

const COURSE_SCOPE: WorkspaceScope = {
  scopeType: 'course',
  scopeLabel: '课程总目录',
};

function clean(value: unknown): string {
  return String(value || '').trim();
}

export function normalizeWorkspaceScope(input?: Partial<WorkspaceScope> | null): WorkspaceScope {
  const scopeType = clean(input?.scopeType) === 'knowledge_point' ? 'knowledge_point' : 'course';
  const scopeId = clean(input?.scopeId) || undefined;
  const scopeLabel = clean(input?.scopeLabel) || undefined;

  if (scopeType === 'knowledge_point' && scopeId) {
    return {
      scopeType,
      scopeId,
      scopeLabel: scopeLabel || scopeId,
    };
  }

  return {
    ...COURSE_SCOPE,
    scopeLabel: COURSE_SCOPE.scopeLabel,
  };
}

export function readWorkspaceScopeFromSearch(searchParams: URLSearchParams): WorkspaceScope {
  return normalizeWorkspaceScope({
    scopeType: (
      searchParams.get('scopeType')
      || searchParams.get('scope_type')
      || searchParams.get('workspaceScopeType')
    ) as WorkspaceScopeType | null,
    scopeId:
      searchParams.get('scopeId')
      || searchParams.get('scope_id')
      || searchParams.get('knowledgePointId')
      || searchParams.get('nodeId'),
    scopeLabel:
      searchParams.get('scopeLabel')
      || searchParams.get('scope_label')
      || searchParams.get('knowledgePointLabel')
      || searchParams.get('nodeLabel'),
  });
}

export function writeWorkspaceScopeToSearch(
  searchParams: URLSearchParams,
  scope: WorkspaceScope,
): URLSearchParams {
  const next = new URLSearchParams(searchParams);
  const normalized = normalizeWorkspaceScope(scope);

  next.set('scopeType', normalized.scopeType);
  if (normalized.scopeType === 'knowledge_point' && normalized.scopeId) {
    next.set('scopeId', normalized.scopeId);
  } else {
    next.delete('scopeId');
  }

  if (normalized.scopeLabel) {
    next.set('scopeLabel', normalized.scopeLabel);
  } else {
    next.delete('scopeLabel');
  }

  return next;
}

export function getWorkspaceScopeApiParams(scope: WorkspaceScope): {
  scopeType: WorkspaceScopeType;
  scopeId?: string;
  aggregate: boolean;
} {
  const normalized = normalizeWorkspaceScope(scope);
  return {
    scopeType: normalized.scopeType,
    scopeId: normalized.scopeId,
    aggregate: normalized.scopeType === 'course',
  };
}

export function getWorkspaceScopeLabel(scope: WorkspaceScope): string {
  const normalized = normalizeWorkspaceScope(scope);
  return normalized.scopeType === 'knowledge_point'
    ? normalized.scopeLabel || normalized.scopeId || '未指定知识点'
    : normalized.scopeLabel || COURSE_SCOPE.scopeLabel || '课程总目录';
}

export function getWorkspaceKnowledgeBaseLabel(scope: WorkspaceScope): string {
  const normalized = normalizeWorkspaceScope(scope);
  if (normalized.scopeType === 'knowledge_point') {
    return `${getWorkspaceScopeLabel(normalized)}知识库`;
  }
  return '课程总知识库';
}
