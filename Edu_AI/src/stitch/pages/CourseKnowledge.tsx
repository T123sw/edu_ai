import { useEffect, useState } from "react";

import { KnowledgeDocumentsView } from "../course/knowledge/KnowledgeDocumentsView";
import { KnowledgeStructureView } from "../course/knowledge/KnowledgeStructureView";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { useAuthSession } from "../authSession";
import { readStudentLocation } from "../student/routes/studentRoutes";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { buildTeacherCourseHash, readTeacherCourseLocation, type CourseKnowledgeView } from "../teacherRoutes";

function currentView(isStudent: boolean): CourseKnowledgeView {
  return isStudent
    ? readStudentLocation(window.location.hash).view ?? "structure"
    : readTeacherCourseLocation(window.location.hash).view ?? "structure";
}

export function CourseKnowledgePage() {
  const { user } = useAuthSession();
  const { courseId } = useCourseRoute();
  const isStudent = user?.role === "student";
  const [view, setView] = useState<CourseKnowledgeView>(() => currentView(isStudent));

  useEffect(() => {
    const sync = () => setView(currentView(isStudent));
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [isStudent]);

  return (
    <div className="course-knowledge">
      <nav className="course-knowledge__tabs" aria-label="课程知识视图">
        <a href={buildRoleCourseHash(user?.role, "knowledge", courseId, { view: "structure" })} aria-current={view === "structure" ? "page" : undefined}>知识图谱</a>
        <a href={buildRoleCourseHash(user?.role, "knowledge", courseId, { view: "documents" })} aria-current={view === "documents" ? "page" : undefined}>课程知识库</a>
      </nav>
      {view === "structure" ? (
        <KnowledgeStructureView buildChatHref={(target) => buildRoleCourseHash(user?.role, "ai", courseId, target)} />
      ) : <KnowledgeDocumentsView readOnly={isStudent} />}
    </div>
  );
}

export function LegacyKnowledgeGraphRedirect() {
  const { courseId } = useCourseRoute();
  useEffect(() => {
    window.location.replace(buildTeacherCourseHash("knowledge", courseId, { view: "structure" }));
  }, [courseId]);
  return null;
}
