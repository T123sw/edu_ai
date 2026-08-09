import type { ComponentType } from "react";

import { StudentAIWorkspacePage } from "./pages/StudentAIWorkspace";
import { StudentClassroomPage } from "./pages/StudentClassroom";
import { StudentCourseKnowledgePage } from "./pages/StudentCourseKnowledge";
import { StudentHomePage } from "./pages/StudentHome";
import { StudentPersonalKnowledgePage } from "./pages/StudentPersonalKnowledge";
import { StudentResourcesPage } from "./pages/StudentResources";
import { StudentRouteGuard } from "./routes/StudentRouteGuard";
import type { StudentRoute } from "./routes/studentRoutes";
import { StudentShell } from "./shell/StudentShell";

const studentPages: Record<StudentRoute, ComponentType> = {
  "student-home": StudentHomePage,
  "student-ai": StudentAIWorkspacePage,
  "student-course-knowledge": StudentCourseKnowledgePage,
  "student-personal-knowledge": StudentPersonalKnowledgePage,
  "student-classroom": StudentClassroomPage,
  "student-resources": StudentResourcesPage,
};

export function StudentApp({ current }: { current: StudentRoute }) {
  const ActivePage = studentPages[current];
  return (
    <StudentRouteGuard>
      <StudentShell activeRoute={current}>
        <ActivePage />
      </StudentShell>
    </StudentRouteGuard>
  );
}
