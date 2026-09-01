import { useMemo, useState } from "react";
import { ClassroomQaPanel } from "../classroomQa/ClassroomQaPanel";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import {
  ClassroomPlaybackSurface,
  type ClassroomQaBinding,
} from "../course/classroomCatalog/ClassroomPlaybackSurface";
import { AppSurface } from "../shared";

function getQueryParams() {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const rawVersion = Number(params.get("resource_version"));
  return {
    courseId: params.get("course_id"),
    classroomId: params.get("classroom_id"),
    resourceVersion: Number.isInteger(rawVersion) && rawVersion > 0 ? rawVersion : undefined,
    catalogNodeId: params.get("catalog_node_id"),
    catalogResourceId: params.get("catalog_resource_id"),
  };
}

export function ClassroomPlayerPage() {
  const target = useMemo(getQueryParams, []);
  const { courseRole } = useCourseRoute();
  const [qaBinding, setQaBinding] = useState<ClassroomQaBinding | null>(null);

  if (!target.courseId || !target.classroomId) {
    return <AppSurface><main className="classroom-console__state">缺少课程或课堂信息，请从 AI 课堂重新进入。</main></AppSurface>;
  }

  return <AppSurface className="min-h-screen">
    <div className="standalone-classroom-player">
      <ClassroomPlaybackSurface
        courseId={target.courseId}
        classroomId={target.classroomId}
        resourceVersion={target.resourceVersion}
        catalogNodeId={target.catalogNodeId}
        catalogResourceId={target.catalogResourceId}
        mode={canCourse(courseRole, "generate") ? "manage" : "learn"}
        onQaControllerChange={setQaBinding}
      />
      {qaBinding ? <ClassroomQaPanel controller={qaBinding.controller} canAsk={qaBinding.canAsk} /> : null}
    </div>
  </AppSurface>;
}
