import { useEffect, useState } from 'react';
import { useAuthSession } from '../authSession';
import { useCourseRoute } from '../course/CourseRouteProvider';
import { recordFromHash, saveResume } from './resumeRecord';
import { validateResume } from './validateResume';
import { resumeApi } from './resumeApi';

export function ResumeTracker() {
  const { user, authenticated } = useAuthSession();
  const { course, courseId, loading, error } = useCourseRoute();
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const sync = () => setHash(window.location.hash);
    window.addEventListener('hashchange', sync);
    window.addEventListener('popstate', sync);
    // Classroom selections use replaceState, which emits no hashchange event.
    const original = window.history.replaceState;
    const replace: History['replaceState'] = function (...args) {
      original.apply(window.history, args);
      sync();
    };
    window.history.replaceState = replace;
    return () => {
      window.removeEventListener('hashchange', sync);
      window.removeEventListener('popstate', sync);
      if (window.history.replaceState === replace) window.history.replaceState = original;
    };
  }, []);
  useEffect(() => {
    if (!authenticated || !user || loading || error || !course || course.id !== courseId) return;
    const record = recordFromHash(user, hash);
    if (!record || record.courseId !== course.id || hash !== window.location.hash) return;
    let cancelled = false;
    void validateResume(user, record, resumeApi).then((result) => {
      if (!cancelled && hash === window.location.hash && result.status === 'valid') saveResume(user, record);
    });
    return () => { cancelled = true; };
  }, [authenticated, user, course, courseId, loading, error, hash]);
  return null;
}
