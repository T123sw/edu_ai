import type { AuthUser } from '../../authSession';
import { readResume } from '../../resume/resumeRecord';

/** Compatibility for the shell's optional default-course hint.
 * Callers without a verified identity must not consume the old unowned history.
 * ResumeEntry and ResumeTracker use the authenticated resume API directly.
 */
export function loadRecentLearning(availableCourseIds?: readonly string[], user?: AuthUser) {
  if (!user || user.role !== 'student') return [];
  const record = readResume(user);
  return record && (!availableCourseIds || availableCourseIds.includes(record.courseId))
    ? [{ courseId: record.courseId, lastRoute: record.route, visitedAt: record.visitedAt }]
    : [];
}
