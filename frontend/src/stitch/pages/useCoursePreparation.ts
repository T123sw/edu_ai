import { useEffect, useState } from 'react';
import type { AuthUser } from '../authSession';
import { getCourseMaterials } from '../api/courses';
import type { CourseMaterial } from '../api/types';
import { readPreparation } from '../resume/resumeRecord';
import { resumeApi } from '../resume/resumeApi';
import { validateResume, type ResumeResult } from '../resume/validateResume';

type History = { key: string; location: ResumeResult | null; material: CourseMaterial | null; materialFailed: boolean; loading: boolean };
export function useCoursePreparation(user: AuthUser | null, courseId?: string) {
  const key = `${user?.role}:${user?.username}:${courseId}`;
  const [history, setHistory] = useState<History | null>(null);
  useEffect(() => {
    if (!user || !courseId) return;
    let cancelled = false;
    const record = readPreparation(user, courseId);
    const location = record ? validateResume(user, record, resumeApi) : Promise.resolve(null);
    const materials = getCourseMaterials(courseId, { space: 'mine', sort: 'updated_desc', limit: 1 })
      .then((items) => ({ material: items[0] ?? null, materialFailed: false }))
      .catch(() => ({ material: null, materialFailed: true }));
    void Promise.all([location, materials]).then(([location, result]) => {
      if (!cancelled) setHistory({ key, location, ...result, loading: false });
    });
    return () => { cancelled = true; };
  }, [user, courseId, key]);
  return history?.key === key ? history : { key, location: null, material: null, materialFailed: false, loading: Boolean(user && courseId) };
}
