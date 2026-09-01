import type {
  ClassroomCatalogResource,
  ResourceQaAnchor,
  ResourceQaKind,
} from '../../api/types';
import type { ClassroomQaController } from '../../classroomQa/classroomQaController';
import { RESOURCE_QA_SCOPE_LABELS, type WorkspaceQaBinding } from './ContextualClassroomQaPanel';

export type ResourceContext = {
  key: string;
  title: string;
  kind: 'classroom' | ResourceQaKind;
  kindLabel: string;
  scopeLabel: string;
  resourceId: string;
  resourceVersion: number | null;
  anchor?: ResourceQaAnchor;
};

export type WorkspaceQaRegistration = ResourceContext & {
  controller: ClassroomQaController;
  canAsk: boolean;
};

export function visibleResourceVersion(
  resource: ClassroomCatalogResource,
  mode: 'manage' | 'learn',
): number | null {
  return mode === 'learn'
    ? resource.approved_version ?? null
    : resource.current_version ?? resource.approved_version ?? null;
}

export function describeOverviewQa() {
  return { key: 'overview', status: 'empty' as const };
}

export function describeCatalogResourceQa(
  resource: ClassroomCatalogResource,
  mode: 'manage' | 'learn',
): ResourceContext & { status: 'loading' } {
  const version = visibleResourceVersion(resource, mode);
  const kind = resource.standard_kind;
  const title = resource.resource?.title || resource.resource?.topic || kindLabel(kind);
  return {
    key: `catalog:${kind}:${resource.material_id}:v${version ?? 'none'}`,
    status: 'loading',
    title,
    kind,
    kindLabel: kindLabel(kind),
    scopeLabel: scopeLabel(kind),
    resourceId: resource.material_id,
    resourceVersion: version,
  };
}

export function describePersonalClassroomQa(
  classroomId: string,
  title: string,
): ResourceContext & { status: 'loading'; version: null } {
  return {
    key: `personal_classroom:${classroomId}`,
    status: 'loading',
    title,
    kind: 'classroom',
    kindLabel: '个人课堂',
    scopeLabel: RESOURCE_QA_SCOPE_LABELS.classroom,
    resourceId: classroomId,
    resourceVersion: null,
    version: null,
  };
}

export function registrationToBinding(
  registration: WorkspaceQaRegistration,
): WorkspaceQaBinding {
  return {
    status: 'ready',
    title: registration.title,
    kindLabel: registration.kindLabel,
    scopeLabel: registration.scopeLabel,
    controller: registration.controller,
    canAsk: registration.canAsk,
  };
}

function kindLabel(kind: ClassroomCatalogResource['standard_kind']): string {
  if (kind === 'study_guide') return '学习指南';
  if (kind === 'practice') return '课程练习';
  return 'AI 课堂';
}

function scopeLabel(kind: ClassroomCatalogResource['standard_kind']): string {
  if (kind === 'study_guide') return RESOURCE_QA_SCOPE_LABELS.document;
  if (kind === 'practice') return RESOURCE_QA_SCOPE_LABELS.practice;
  return RESOURCE_QA_SCOPE_LABELS.classroom;
}
