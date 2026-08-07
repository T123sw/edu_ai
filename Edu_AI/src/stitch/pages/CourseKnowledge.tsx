import { useEffect, useState } from "react";

import { KnowledgeDocumentsView } from "../course/knowledge/KnowledgeDocumentsView";
import { KnowledgeStructureView } from "../course/knowledge/KnowledgeStructureView";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { buildTeacherCourseHash, readTeacherCourseLocation, type CourseKnowledgeView } from "../teacherRoutes";

function currentView(): CourseKnowledgeView {
  return readTeacherCourseLocation(window.location.hash).view ?? "structure";
}

export function CourseKnowledgePage() {
  const { courseId } = useCourseRoute();
  const [view, setView] = useState<CourseKnowledgeView>(currentView);

  useEffect(() => {
    const sync = () => setView(currentView());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  return (
    <div className="course-knowledge">
      <nav className="course-knowledge__tabs" aria-label="课程知识视图">
        <a href={buildTeacherCourseHash("knowledge", courseId, { view: "structure" })} aria-current={view === "structure" ? "page" : undefined}>知识图谱</a>
        <a href={buildTeacherCourseHash("knowledge", courseId, { view: "documents" })} aria-current={view === "documents" ? "page" : undefined}>课程知识库</a>
      </nav>
      {view === "structure" ? <KnowledgeStructureView /> : <KnowledgeDocumentsView />}
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
