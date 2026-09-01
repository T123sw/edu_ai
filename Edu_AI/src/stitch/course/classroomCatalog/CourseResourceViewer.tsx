import type { ClassroomCatalogResource } from "../../api/types";
import { CourseMaterialArtifactPreview } from "../../pages/CourseMaterialArtifactPreview";
import { ClassroomPlaybackSurface, type ClassroomQaBinding } from "./ClassroomPlaybackSurface";
import { catalogResourceLabel, catalogResourceStatus } from "./catalogPresentation";
import { StudentPracticeView } from "./StudentPracticeView";
import { StudentReadingView } from "./StudentReadingView";
import { TeacherResourceReviewPanel } from "./TeacherResourceReviewPanel";

type Props = {
  courseId: string;
  nodeId: string;
  resource: ClassroomCatalogResource;
  mode: "manage" | "learn";
  onChanged: (materialId: string) => void | Promise<void>;
  onQaControllerChange?: (binding: ClassroomQaBinding | null) => void;
};

export function CourseResourceViewer({ courseId, nodeId, resource, mode, onChanged, onQaControllerChange }: Props) {
  if (resource.standard_kind === "classroom") return <>
    <ClassroomPlaybackSurface
      courseId={courseId}
      classroomId={resource.material_id}
      resourceVersion={(mode === "learn" ? resource.approved_version : resource.current_version) ?? undefined}
      catalogNodeId={nodeId}
      catalogResourceId={resource.material_id}
      mode={mode}
      onQaControllerChange={onQaControllerChange}
    />
    {mode === "manage" ? <TeacherResourceReviewPanel courseId={courseId} resource={resource} onChanged={onChanged} /> : null}
  </>;
  if (mode === "learn" && resource.standard_kind === "study_guide") return <StudentReadingView courseId={courseId} resource={resource} onProgress={() => void onChanged(resource.material_id)} />;
  if (mode === "learn" && resource.standard_kind === "practice") return <StudentPracticeView courseId={courseId} resource={resource} onProgress={() => void onChanged(resource.material_id)} />;
  return <section className="course-resource-viewer"><header><div><p className="curriculum-node-overview__eyebrow">课程资料</p><h2>{catalogResourceLabel(resource)}</h2></div>
    <span className={`catalog-status is-${resource.review_status}`}>{catalogResourceStatus(resource)}</span></header>
    {resource.resource ? <CourseMaterialArtifactPreview material={resource.resource} /> : <p className="catalog-panel-message">该资源尚无可预览内容。</p>}
    <TeacherResourceReviewPanel courseId={courseId} resource={resource} onChanged={onChanged} />
  </section>;
}
