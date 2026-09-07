import type { AuthUser } from '../authSession';
import { buildTeacherCourseHash, type TeacherCourseRoute } from '../teacherRoutes';
import { buildStudentHash, type StudentRoute } from '../student/routes/studentRoutes';
import { readWorkspaceScopeFromSearch } from '../../services/teacher/workspaceScope';

export type ResumeRecord = {
  version: 1;
  courseId: string;
  route: string;
  params: Record<string, string>;
  visitedAt: string;
};
export type ResumeStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
const teacherRoutes = new Set(['course-detail', 'ai', 'knowledge', 'resources', 'classroom-studio', 'learning']);
const studentRoutes = new Set(['student-course-detail', 'student-ai', 'student-course-knowledge', 'student-resources', 'student-classroom', 'student-learning']);
const validId = (value: string | null): value is string => Boolean(value && value.length <= 256 && !/[\s/\\?#\u0000-\u001f]/.test(value) && value !== 'null' && value !== 'undefined');
export const resumeKey = (user: AuthUser) => `edu-ai-resume:v1:${user.role}:${encodeURIComponent(user.username)}`;

export function recordFromHash(user: AuthUser, hash: string, now = new Date()): ResumeRecord | null {
  if (!hash.startsWith('#')) return null;
  const [name, query = ''] = hash.slice(1).split('?');
  const route = name === 'teacher-classroom-studio' ? 'classroom-studio' : name;
  if (!(user.role === 'student' ? studentRoutes : teacherRoutes).has(route)) return null;
  const search = new URLSearchParams(query);
  const courseId = search.get('course_id');
  if (!validId(courseId)) return null;
  const params: Record<string, string> = {};
  if (route === 'ai' || route === 'student-ai') {
    const scope = readWorkspaceScopeFromSearch(search);
    if (scope.scopeType === 'knowledge_point' && validId(scope.scopeId ?? null)) {
      params.scopeType = 'knowledge_point';
      params.scopeId = scope.scopeId!;
    }
  }
  const fields = route.endsWith('resources') ? ['material_type', 'material_id']
    : route === 'classroom-studio' || route === 'student-classroom' ? ['node_id', 'resource_id', 'personal_classroom_id'] : [];
  for (const key of fields) {
    const value = search.get(key);
    if (validId(value)) params[key] = value;
  }
  if (Boolean(params.material_id) !== Boolean(params.material_type)) return null;
  if (params.resource_id && !params.node_id) return null;
  if (params.personal_classroom_id && (params.node_id || params.resource_id)) return null;
  return { version: 1, courseId, route, params, visitedAt: now.toISOString() };
}

export function resumeHash(user: AuthUser, record: ResumeRecord): string {
  if (user.role !== 'student') return buildTeacherCourseHash(record.route as TeacherCourseRoute, record.courseId, record.params);
  const p = record.params;
  const hash = buildStudentHash(record.route as StudentRoute, {
    courseId: record.courseId, scopeType: p.scopeType as 'knowledge_point' | undefined,
    scopeId: p.scopeId, materialType: p.material_type, materialId: p.material_id,
    nodeId: p.node_id, resourceId: p.resource_id,
  });
  // The classroom workspace owns this existing parameter (studentRoutes omits it).
  return p.personal_classroom_id ? `${hash}&personal_classroom_id=${encodeURIComponent(p.personal_classroom_id)}` : hash;
}

export function parseResume(user: AuthUser, raw: string | null): ResumeRecord | null {
  try {
    const value = JSON.parse(raw ?? 'null');
    if (!value || value.version !== 1 || typeof value.courseId !== 'string' || typeof value.route !== 'string' || !value.params || typeof value.params !== 'object' || typeof value.visitedAt !== 'string' || !Number.isFinite(Date.parse(value.visitedAt))) return null;
    const query = new URLSearchParams({ course_id: value.courseId });
    for (const [key, item] of Object.entries(value.params)) {
      if (key !== 'course_id' && typeof item === 'string') query.set(key, item);
    }
    return recordFromHash(user, `#${value.route}?${query}`, new Date(value.visitedAt));
  } catch { return null; }
}

export function readResume(user: AuthUser, storage: () => ResumeStorage = () => window.localStorage) {
  try { return parseResume(user, storage().getItem(resumeKey(user))); } catch { return null; }
}
export function saveResume(user: AuthUser, record: ResumeRecord | null, storage: () => ResumeStorage = () => window.localStorage) {
  try {
    if (!record) storage().removeItem(resumeKey(user));
    else {
      const clean = parseResume(user, JSON.stringify(record));
      if (clean) storage().setItem(resumeKey(user), JSON.stringify(clean));
    }
  } catch { /* History must never prevent navigation. */ }
}
