import type { AuthUser } from '../authSession';
import type { CourseRole } from '../course/coursePermissions';

export function shouldTrackResourceLearning({
  role,
  courseRole,
  resourceVersion,
}: {
  role: AuthUser['role'] | undefined;
  courseRole: CourseRole | null | undefined;
  resourceVersion: number | null;
}): boolean {
  return (
    role === 'student' &&
    courseRole === 'viewer' &&
    Number.isInteger(resourceVersion) &&
    (resourceVersion ?? 0) > 0
  );
}
