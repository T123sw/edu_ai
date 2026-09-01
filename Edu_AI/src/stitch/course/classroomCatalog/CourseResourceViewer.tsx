import type { ClassroomCatalogResource } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { buildClassroomPlayerHash } from "../../../openmaic/classroomGenerationFlow";
import { CourseMaterialArtifactPreview } from "../../pages/CourseMaterialArtifactPreview";
import { catalogResourceLabel, catalogResourceStatus } from "./catalogPresentation";
import { StudentPracticeView } from "./StudentPracticeView";
import { StudentReadingView } from "./StudentReadingView";
import { StudentResourceProgressPanel } from "./StudentResourceProgressPanel";
import { TeacherResourceReviewPanel } from "./TeacherResourceReviewPanel";

type Props = { courseId: string; nodeId: string; resource: ClassroomCatalogResource; mode: "manage" | "learn"; onChanged: (materialId: string) => void | Promise<void> };

function ClassroomCatalogCard({ courseId, nodeId, resource, mode }: Omit<Props, "onChanged">) {
  const version = resource.approved_version ?? resource.current_version ?? null;
  const href = buildClassroomPlayerHash(courseId, resource.material_id, mode === "learn" ? {
    resourceVersion: version,
    catalogNodeId: nodeId,
    catalogResourceId: resource.material_id,
  } : undefined);
  return <section className="course-resource-viewer__classroom">
    <div className="course-resource-viewer__classroom-art"><MaterialIcon name="play_circle" /></div>
    <p className="curriculum-node-overview__eyebrow">互动 AI 课堂</p><h2>{catalogResourceLabel(resource)}</h2>
    <p>进入课堂后可按场景学习讲解、互动演示并完成随堂问题。</p>
    {mode === "learn" ? <StudentResourceProgressPanel progress={resource.progress} /> : null}
    <a className="catalog-primary-action" href={href}><MaterialIcon name="play_arrow" />{mode === "learn" ? "进入课堂学习" : "预览课堂"}</a>
  </section>;
}

export function CourseResourceViewer({ courseId, nodeId, resource, mode, onChanged }: Props) {
  if (resource.standard_kind === "classroom") return <>
    <ClassroomCatalogCard courseId={courseId} nodeId={nodeId} resource={resource} mode={mode} />
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
