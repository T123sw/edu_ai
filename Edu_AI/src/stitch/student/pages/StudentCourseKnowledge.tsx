import { useEffect, useState } from "react";

import { KnowledgeDocumentsView } from "../../course/knowledge/KnowledgeDocumentsView";
import { KnowledgeStructureView } from "../../course/knowledge/KnowledgeStructureView";
import { useCourseRoute } from "../../course/CourseRouteProvider";
import { buildStudentHash, readStudentLocation, type StudentCourseKnowledgeView } from "../routes/studentRoutes";
import { saveRecentLearningVisit } from "./studentRecentLearning";
import "../styles/studentKnowledge.css";

function currentView(): StudentCourseKnowledgeView {
  return readStudentLocation(window.location.hash).view ?? "structure";
}

export function StudentCourseKnowledgePage() {
  const { courseId } = useCourseRoute();
  const [view, setView] = useState<StudentCourseKnowledgeView>(currentView);

  useEffect(() => {
    const sync = () => setView(currentView());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  useEffect(() => { if (courseId) saveRecentLearningVisit(courseId, "student-course-knowledge"); }, [courseId]);

  return (
    <div className="student-course-knowledge">
      <nav className="student-knowledge-tabs" aria-label="课程知识视图">
        <a href={buildStudentHash("student-course-knowledge", { courseId, view: "structure" })} aria-current={view === "structure" ? "page" : undefined}>知识图谱</a>
        <a href={buildStudentHash("student-course-knowledge", { courseId, view: "documents" })} aria-current={view === "documents" ? "page" : undefined}>课程知识库</a>
      </nav>
      {view === "structure" ? (
        <KnowledgeStructureView buildChatHref={(target) => buildStudentHash("student-ai", { courseId, ...target })} />
      ) : <KnowledgeDocumentsView readOnly />}
    </div>
  );
}
