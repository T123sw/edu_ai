/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import type { ApiError } from "../api/client";
import type { BackendCourse } from "../api/types";
import { readTeacherCourseId } from "../teacherRoutes";
import { readStudentLocation } from "../student/routes/studentRoutes";
import type { CourseRole } from "./coursePermissions";

export type CourseRouteValue = {
  courseId: string | null;
  course: BackendCourse | null;
  courseRole: CourseRole | null;
  loading: boolean;
  error: ApiError | null;
  reload: () => Promise<void>;
};

type CourseRouteState = { courseId: string | null };

function routeName(hash: string): string {
  return String(hash || "").replace(/^#/, "").split("?")[0];
}

export function resolveCourseRouteState(
  hash: string,
  rememberedCourseId: string | null | undefined,
): CourseRouteState {
  const fromUrl = readTeacherCourseId(hash) ?? readStudentLocation(hash).courseId;
  if (fromUrl) return { courseId: fromUrl };
  const remembered = String(rememberedCourseId ?? "").trim();
  return {
    courseId:
      routeName(hash) === "home" &&
      remembered &&
      remembered !== "undefined" &&
      remembered !== "null"
        ? remembered
        : null,
  };
}

const emptyValue: CourseRouteValue = {
  courseId: null,
  course: null,
  courseRole: null,
  loading: false,
  error: null,
  reload: async () => undefined,
};

const CourseRouteContext = createContext<CourseRouteValue>(emptyValue);

export function CourseRouteProvider({
  children,
  rememberedCourseId,
  enabled,
}: PropsWithChildren<{
  rememberedCourseId?: string | null;
  enabled: boolean;
}>) {
  const [hash, setHash] = useState(() =>
    typeof window === "undefined" ? "#home" : window.location.hash || "#home",
  );
  const { courseId } = resolveCourseRouteState(hash, rememberedCourseId);
  const [course, setCourse] = useState<BackendCourse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const sync = () => setHash(window.location.hash || "#home");
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const reload = useCallback(async () => {
    if (!enabled || !courseId) {
      setCourse(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { getCourse } = await import("../api/courses");
      const loaded = await getCourse(courseId);
      setCourse(loaded);
    } catch (reason) {
      setCourse(null);
      const fallback = new Error(
        reason instanceof Error ? reason.message : "课程加载失败",
      ) as ApiError;
      fallback.status =
        typeof reason === "object" && reason !== null && "status" in reason
          ? Number(reason.status) || 0
          : 0;
      setError(fallback);
    } finally {
      setLoading(false);
    }
  }, [courseId, enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo<CourseRouteValue>(
    () => ({
      courseId,
      course,
      courseRole: course?.membership_role ?? null,
      loading,
      error,
      reload,
    }),
    [course, courseId, error, loading, reload],
  );

  return <CourseRouteContext.Provider value={value}>{children}</CourseRouteContext.Provider>;
}

export function useCourseRoute() {
  return useContext(CourseRouteContext);
}
