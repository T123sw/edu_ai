import { getLearningOverview } from '../api/learning';
import { getCourse, getKnowledgeGraph, getCourseMaterials } from '../api/courses';
import { getClassroomCatalog } from '../api/classroomCatalog';
import { listClassrooms } from '../api/classroom';
import type { ResumeApi } from './validateResume';
export const resumeApi: ResumeApi = {
  overview: getLearningOverview, course: getCourse, graph: getKnowledgeGraph,
  materials: (id) => getCourseMaterials(id, { space: 'mine' }),
  catalog: getClassroomCatalog, classrooms: (id) => listClassrooms(id, 'mine'),
};
