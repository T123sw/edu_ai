import type { AuthUser } from '../authSession';
import type { ResumeRecord } from './resumeRecord';
import type { BackendCourse, KnowledgeGraphNode, ClassroomCatalog, ClassroomMaterial, CourseMaterial } from '../api/types';

export type ResumeApi = {
  course: (id: string) => Promise<BackendCourse>;
  graph: (id: string) => Promise<{ root: KnowledgeGraphNode }>;
  materials: (id: string) => Promise<CourseMaterial[]>;
  catalog: (id: string) => Promise<ClassroomCatalog>;
  classrooms: (id: string) => Promise<ClassroomMaterial[]>;
  overview: (id: string) => Promise<unknown>;
};
export type ResumeResult =
  | { status: 'valid' | 'fallback'; course: BackendCourse; record: ResumeRecord; label?: string }
  | { status: 'invalid' | 'retry' };
const unavailable = (reason: unknown) => typeof reason === 'object' && reason !== null && 'status' in reason && [403, 404, 410].includes(Number(reason.status));
function findNode(node: KnowledgeGraphNode, id: string): KnowledgeGraphNode | undefined {
  if (node.id === id) return node;
  for (const child of node.children ?? []) { const found = findNode(child, id); if (found) return found; }
}
export async function validateResume(user: AuthUser, record: ResumeRecord, api: ResumeApi): Promise<ResumeResult> {
  let course: BackendCourse;
  try { course = await api.course(record.courseId); }
  catch (reason) { return { status: unavailable(reason) ? 'invalid' : 'retry' }; }
  if (course.id !== record.courseId) return { status: 'retry' };
  const fallback = (): ResumeResult => ({ status: 'fallback', course, record: { ...record, route: user.role === 'student' ? 'student-course-detail' : 'course-detail', params: {} } });
  const p = record.params;
  let label: string | undefined;
  try {
    if (p.scopeId || record.route === 'knowledge' || record.route === 'student-course-knowledge') {
      const graph = await api.graph(course.id);
      if (p.scopeId) {
        const node = findNode(graph.root, p.scopeId);
        if (!node) return fallback();
        label = node.label;
      }
    }
    if (record.route.endsWith('resources')) {
      const materials = await api.materials(course.id);
      if (p.material_id && !materials.some((item) => item.material_id === p.material_id && item.material_type === p.material_type)) return fallback();
    }
    if ((record.route === 'classroom-studio' || record.route === 'student-classroom') && !p.personal_classroom_id) {
      const catalog = await api.catalog(course.id);
      const node = catalog.leaves.find((leaf) => leaf.leaf_id === p.node_id);
      if (p.node_id && (!node || (p.resource_id && !node.resources.some((resource) => resource.material_id === p.resource_id && resource.resource)))) return fallback();
    }
    if (record.route === 'learning' || record.route === 'student-learning') await api.overview(course.id);
    if (p.personal_classroom_id && !(await api.classrooms(course.id)).some((item) => item.material_id === p.personal_classroom_id)) return fallback();
  } catch (reason) { return unavailable(reason) ? fallback() : { status: 'retry' }; }
  return { status: 'valid', course, record, label };
}
