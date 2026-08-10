import { useEffect, type ComponentType } from "react";

import { CourseShell } from "../course/CourseShell";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { AIWorkspacePage } from "../pages/AIWorkspace";
import { ClassroomStudioPage } from "../pages/ClassroomStudio";
import { CourseDetailPage } from "../pages/CourseDetail";
import { CourseKnowledgePage } from "../pages/CourseKnowledge";
import { CourseResourcesPage } from "../pages/CourseResources";
import { CourseLearningPage } from "../pages/CourseLearning";
import { StudentHomePage } from "./pages/StudentHome";
import { StudentPersonalKnowledgePage } from "./pages/StudentPersonalKnowledge";
import { StudentRouteGuard } from "./routes/StudentRouteGuard";
import type { StudentRoute } from "./routes/studentRoutes";
import { StudentShell } from "./shell/StudentShell";
import { saveRecentLearningVisit } from "./pages/studentRecentLearning";

const studentPages: Record<StudentRoute, ComponentType> = {
  "student-home": StudentHomePage,
  "student-course-detail": CourseDetailPage,
  "student-learning": CourseLearningPage,
  "student-ai": AIWorkspacePage,
  "student-course-knowledge": CourseKnowledgePage,
  "student-personal-knowledge": StudentPersonalKnowledgePage,
  "student-classroom": ClassroomStudioPage,
  "student-resources": CourseResourcesPage,
};

const courseWorkspaceRoutes = new Set<StudentRoute>([
  "student-course-detail",
  "student-learning",
  "student-ai",
  "student-course-knowledge",
  "student-classroom",
  "student-resources",
]);

function RecentLearningTracker({ route }: { route: StudentRoute }) {
  const { courseId } = useCourseRoute();
  useEffect(() => {
    if (courseId) saveRecentLearningVisit(courseId, route);
  }, [courseId, route]);
  return null;
}

export function StudentApp({ current }: { current: StudentRoute }) {
  const ActivePage = studentPages[current];
  const inCourseWorkspace = courseWorkspaceRoutes.has(current);
  return (
    <StudentRouteGuard>
      {inCourseWorkspace ? (
        <CourseShell activeRoute={current}>
          <RecentLearningTracker route={current} />
          <ActivePage />
        </CourseShell>
      ) : (
        <StudentShell activeRoute={current}>
          <ActivePage />
        </StudentShell>
      )}
    </StudentRouteGuard>
  );
}
