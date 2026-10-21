import type { EduJob } from '../stitch/api/types.ts';

export const PENDING_CLASSROOM_GENERATION_STORAGE_KEY =
  'edu-ai-pending-classroom-generations-v1';

export interface ClassroomGenerationStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface PendingClassroomGeneration {
  courseId: string;
  topic: string;
  job: EduJob;
  savedAt: string;
}

type PendingClassroomGenerationMap = Record<
  string,
  PendingClassroomGeneration
>;

function isEduJob(value: unknown): value is EduJob {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const candidate = value as Partial<EduJob>;
  return (
    typeof candidate.edu_job_id === 'string' &&
    typeof candidate.kind === 'string' &&
    typeof candidate.status === 'string' &&
    typeof candidate.step === 'string' &&
    typeof candidate.progress === 'number' &&
    typeof candidate.message === 'string' &&
    typeof candidate.created_at === 'string' &&
    typeof candidate.updated_at === 'string'
  );
}

function isPendingClassroomGeneration(
  value: unknown,
): value is PendingClassroomGeneration {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const candidate = value as Partial<PendingClassroomGeneration>;
  return (
    typeof candidate.courseId === 'string' &&
    typeof candidate.topic === 'string' &&
    typeof candidate.savedAt === 'string' &&
    isEduJob(candidate.job)
  );
}

function readMap(
  storage: ClassroomGenerationStorage,
): PendingClassroomGenerationMap {
  const raw = storage.getItem(PENDING_CLASSROOM_GENERATION_STORAGE_KEY);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Invalid classroom generation recovery map');
    }

    const validEntries = Object.entries(parsed).filter(
      ([courseId, value]) =>
        isPendingClassroomGeneration(value) && value.courseId === courseId,
    );
    return Object.fromEntries(validEntries);
  } catch {
    storage.removeItem(PENDING_CLASSROOM_GENERATION_STORAGE_KEY);
    return {};
  }
}

function writeMap(
  storage: ClassroomGenerationStorage,
  pending: PendingClassroomGenerationMap,
): void {
  if (Object.keys(pending).length === 0) {
    storage.removeItem(PENDING_CLASSROOM_GENERATION_STORAGE_KEY);
    return;
  }
  storage.setItem(
    PENDING_CLASSROOM_GENERATION_STORAGE_KEY,
    JSON.stringify(pending),
  );
}

export function readPendingClassroomGeneration(
  storage: ClassroomGenerationStorage,
  courseId: string,
): PendingClassroomGeneration | null {
  try {
    return readMap(storage)[courseId] ?? null;
  } catch {
    return null;
  }
}

export function savePendingClassroomGeneration(
  storage: ClassroomGenerationStorage,
  pending: PendingClassroomGeneration,
): void {
  try {
    const current = readMap(storage);
    current[pending.courseId] = pending;
    writeMap(storage, current);
  } catch {
    // Recovery storage must never interrupt classroom generation itself.
  }
}

export function clearPendingClassroomGeneration(
  storage: ClassroomGenerationStorage,
  courseId: string,
  eduJobId: string,
): void {
  try {
    const current = readMap(storage);
    if (current[courseId]?.job.edu_job_id !== eduJobId) {
      return;
    }
    delete current[courseId];
    writeMap(storage, current);
  } catch {
    // A cleanup failure can safely leave the record for the next page load.
  }
}
