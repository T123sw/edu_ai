import { useEffect } from "react";

import { KnowledgeDocumentsView } from "../course/knowledge/KnowledgeDocumentsView";
import { StandardLearningResources } from "../course/knowledge/StandardLearningResources";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { useAuthSession } from "../authSession";
import { buildTeacherCourseHash } from "../teacherRoutes";

export function CourseKnowledgePage() {
  const { user } = useAuthSession();
  const isStudent = user?.role === "student";

  return (
    <div className="course-knowledge">
      <KnowledgeDocumentsView readOnly={isStudent} />
      {isStudent ? <StandardLearningResources readOnly /> : null}
    </div>
  );
}

export function LegacyKnowledgeGraphRedirect() {
  const { courseId } = useCourseRoute();
  useEffect(() => {
    window.location.replace(buildTeacherCourseHash("knowledge", courseId));
  }, [courseId]);
  return null;
}
