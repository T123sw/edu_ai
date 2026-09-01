import { useEffect, useState } from "react";
import type { ClassroomCatalogResource, ResourceQaAnchor } from "../../api/types";
import { useStaticResourceQa } from "../../classroomQa/useStaticResourceQa";
import { CourseMaterialArtifactPreview } from "../../pages/CourseMaterialArtifactPreview";
import { ClassroomPlaybackSurface } from "./ClassroomPlaybackSurface";
import { catalogResourceLabel, catalogResourceStatus } from "./catalogPresentation";
import { StudentPracticeView } from "./StudentPracticeView";
import { StudentReadingView } from "./StudentReadingView";
import { TeacherResourceReviewPanel } from "./TeacherResourceReviewPanel";
import {
  describeCatalogResourceQa,
  type ResourceContext,
  type WorkspaceQaRegistration,
} from "./workspaceQaBinding";

type Props = {
  courseId: string;
  nodeId: string;
  resource: ClassroomCatalogResource;
  mode: "manage" | "learn";
  onChanged: (materialId: string) => void | Promise<void>;
  onQaControllerChange?: (targetKey: string, binding: WorkspaceQaRegistration | null) => void;
};

export function CourseResourceViewer({ courseId, nodeId, resource, mode, onChanged, onQaControllerChange }: Props) {
  const context = describeCatalogResourceQa(resource, mode);
  const [anchor, setAnchor] = useState<ResourceQaAnchor | undefined>();
  useEffect(() => setAnchor(undefined), [context.key]);

  if (resource.standard_kind === "classroom") return <>
    <ClassroomPlaybackSurface
      courseId={courseId}
      classroomId={resource.material_id}
      resourceVersion={(mode === "learn" ? resource.approved_version : resource.current_version) ?? undefined}
      catalogNodeId={nodeId}
      catalogResourceId={resource.material_id}
      mode={mode}
      qaTargetKey={context.key}
      onQaControllerChange={onQaControllerChange}
    />
    {mode === "manage" ? <TeacherResourceReviewPanel courseId={courseId} resource={resource} onChanged={onChanged} /> : null}
  </>;
  if (mode === "learn" && resource.standard_kind === "study_guide") return <>
    <StaticResourceQaBridge courseId={courseId} context={context} onChange={onQaControllerChange} />
    <StudentReadingView courseId={courseId} resource={resource} onProgress={() => void onChanged(resource.material_id)} />
  </>;
  if (mode === "learn" && resource.standard_kind === "practice") return <>
    <StaticResourceQaBridge courseId={courseId} context={context} anchor={anchor} onChange={onQaControllerChange} />
    <StudentPracticeView courseId={courseId} resource={resource} onProgress={() => void onChanged(resource.material_id)} onQuestionFocus={(questionId) => setAnchor(questionId ? { question_id: questionId } : undefined)} />
  </>;
  return <>
    {resource.standard_kind !== "classroom" ? <StaticResourceQaBridge courseId={courseId} context={context} anchor={anchor} onChange={onQaControllerChange} /> : null}
    <section className="course-resource-viewer"><header><div><p className="curriculum-node-overview__eyebrow">课程资料</p><h2>{catalogResourceLabel(resource)}</h2></div>
    <span className={`catalog-status is-${resource.review_status}`}>{catalogResourceStatus(resource)}</span></header>
    {resource.resource ? <CourseMaterialArtifactPreview material={resource.resource} /> : <p className="catalog-panel-message">该资源尚无可预览内容。</p>}
    <TeacherResourceReviewPanel courseId={courseId} resource={resource} onChanged={onChanged} />
    </section>
  </>;
}

function StaticResourceQaBridge({
  courseId,
  context,
  anchor,
  onChange,
}: {
  courseId: string;
  context: ResourceContext;
  anchor?: ResourceQaAnchor;
  onChange?: (targetKey: string, binding: WorkspaceQaRegistration | null) => void;
}) {
  if (context.kind === "classroom" || !context.resourceVersion) return null;
  return <ActiveStaticResourceQaBridge courseId={courseId} context={context} anchor={anchor} onChange={onChange} />;
}

function ActiveStaticResourceQaBridge({
  courseId,
  context,
  anchor,
  onChange,
}: {
  courseId: string;
  context: ResourceContext & { kind: "study_guide" | "practice" };
  anchor?: ResourceQaAnchor;
  onChange?: (targetKey: string, binding: WorkspaceQaRegistration | null) => void;
}) {
  const controller = useStaticResourceQa({
    courseId,
    kind: context.kind,
    resourceId: context.resourceId,
    resourceVersion: context.resourceVersion!,
    anchor,
  });
  useEffect(() => {
    onChange?.(context.key, { ...context, controller, canAsk: true });
    return () => onChange?.(context.key, null);
  }, [context.key, context.kindLabel, context.resourceId, context.resourceVersion, context.scopeLabel, context.title, controller, onChange]);
  return null;
}
