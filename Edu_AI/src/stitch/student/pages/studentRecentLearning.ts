import type { StudentRoute } from "../routes/studentRoutes";

export const STUDENT_RECENT_LEARNING_KEY = "edu-ai-student-recent-learning";
const VERSION = 1;
const LIMIT = 1;
const allowedRoutes = new Set<StudentRoute>([
  "student-course-detail",
  "student-ai",
  "student-course-knowledge",
  "student-classroom",
  "student-resources",
]);

export type RecentLearningRecord = {
  courseId: string;
  lastRoute: StudentRoute;
  visitedAt: string;
};

function sanitizeRecord(value: unknown): RecentLearningRecord | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const courseId = typeof record.courseId === "string" ? record.courseId.trim() : "";
  const lastRoute = typeof record.lastRoute === "string" ? record.lastRoute : "";
  const timestamp = typeof record.visitedAt === "string" ? Date.parse(record.visitedAt) : Number.NaN;
  if (!courseId || !allowedRoutes.has(lastRoute as StudentRoute) || !Number.isFinite(timestamp)) return null;
  return { courseId, lastRoute: lastRoute as StudentRoute, visitedAt: new Date(timestamp).toISOString() };
}

function normalizeRecords(records: unknown[], availableCourseIds?: readonly string[]): RecentLearningRecord[] {
  const allowedCourses = availableCourseIds ? new Set(availableCourseIds) : null;
  const newestByCourse = new Map<string, RecentLearningRecord>();
  for (const value of records) {
    const record = sanitizeRecord(value);
    if (!record || (allowedCourses && !allowedCourses.has(record.courseId))) continue;
    const current = newestByCourse.get(record.courseId);
    if (!current || Date.parse(record.visitedAt) > Date.parse(current.visitedAt)) {
      newestByCourse.set(record.courseId, record);
    }
  }
  return [...newestByCourse.values()]
    .sort((left, right) => Date.parse(right.visitedAt) - Date.parse(left.visitedAt))
    .slice(0, LIMIT);
}

export function parseRecentLearning(raw: string | null, availableCourseIds?: readonly string[]): RecentLearningRecord[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw) as { version?: unknown; records?: unknown };
    if (value.version !== VERSION || !Array.isArray(value.records)) return [];
    return normalizeRecords(value.records, availableCourseIds);
  } catch {
    return [];
  }
}

export function recordRecentLearning(
  current: readonly RecentLearningRecord[],
  visit: RecentLearningRecord,
): RecentLearningRecord[] {
  return normalizeRecords([visit, ...current]);
}

export function serializeRecentLearning(records: readonly RecentLearningRecord[]): string {
  return JSON.stringify({ version: VERSION, records: normalizeRecords([...records]) });
}

export function loadRecentLearning(availableCourseIds?: readonly string[]): RecentLearningRecord[] {
  return parseRecentLearning(window.localStorage.getItem(STUDENT_RECENT_LEARNING_KEY), availableCourseIds);
}

export function saveRecentLearningVisit(courseId: string, lastRoute: StudentRoute, now = new Date()): void {
  const current = loadRecentLearning();
  const next = recordRecentLearning(current, { courseId, lastRoute, visitedAt: now.toISOString() });
  window.localStorage.setItem(STUDENT_RECENT_LEARNING_KEY, serializeRecentLearning(next));
}
