import type { StatusCardV2 } from '../../services/teacher/chatV2';
import type { Course } from '../../store/course/useCourseStore';

export function getAiStudioCourseLabel(currentCourse: Course | null, courseId?: string): string {
  const title = String(currentCourse?.title || '').trim();
  if (title) {
    return title;
  }

  const fallbackCourseId = String(courseId || '').trim();
  return fallbackCourseId || '未指定课程';
}

export function getAiStudioKnowledgePointLabel(statusCard: StatusCardV2 | null): string {
  const firstTopic = Array.isArray(statusCard?.topics)
    ? statusCard.topics.map((item) => String(item || '').trim()).find(Boolean)
    : '';

  return firstTopic || '未指定知识点';
}
