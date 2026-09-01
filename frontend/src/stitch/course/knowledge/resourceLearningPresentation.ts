import { buildClassroomPlayerHash } from '../../../openmaic/classroomGenerationFlow';
import type { ResourceLearningProgress } from '../../api/types';

export function buildStudentClassroomLearningHref(
  courseId: string,
  classroomId: string,
  approvedVersion: number,
): string {
  const base = buildClassroomPlayerHash(courseId, classroomId);
  return `${base}&resource_version=${encodeURIComponent(String(approvedVersion))}`;
}

export function resourceLearningLabels(progress: ResourceLearningProgress): {
  coverage: string;
  questions: string;
  status: string;
} {
  const coverage = Math.max(
    0,
    Math.min(100, Math.round(progress.explanation_coverage_percent)),
  );
  const behaviorOnly = progress.manifest?.mode === 'behavior_only';
  return {
    coverage: `讲解完整度 ${coverage}%`,
    questions: `习题进度 ${progress.answered_question_count}/${progress.required_question_count}`,
    status: behaviorOnly
      ? '已记录学习行为'
      : progress.status === 'completed'
        ? '已完成'
        : progress.status === 'in_progress'
          ? '学习中'
          : '尚未开始',
  };
}

export function resourceLearningProgressKey(
  resourceId: string,
  version: number,
): string {
  return `${resourceId}:${version}`;
}
