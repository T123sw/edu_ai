import { DraftDocumentPreview, useDraftPreview } from "../../stitch/artifactRevision/draftPreview";
import { lazy, Suspense, useEffect, useState, type FC } from "react";

import type { WorkspaceScope } from "../../services/teacher/workspaceScope";
import { GenerationFactory, type GenerationResultTarget } from "../generation/GenerationFactory";
import { getCourseMaterial } from "../../stitch/api/courses";
import type { CourseMaterial } from "../../stitch/api/types";
import { CourseMaterialArtifactPreview } from "../../stitch/pages/CourseMaterialArtifactPreview";
import { MaterialIcon } from "../../stitch/shared";
import "../../stitch/pages/courseResources.css";
import "../../stitch/course/classroomCatalog/courseClassroomCatalog.css";

import { createRevisionIntent, dispatchRevisionIntent } from "../../stitch/artifactRevision/intent";
import { getGenerationTools } from "../../stitch/api/generationTools";
import type { GenerationToolId } from "../../stitch/shared/generation/generationCatalog";
import { useAuthSession } from "../../stitch/authSession";
import { buildRoleCourseHash } from "../../stitch/shared/routes/roleCourseRouteResolver";
import { useStore } from "../../store/teacher/useStore";

const ClassroomPlaybackSurface = lazy(() => import("../../stitch/course/classroomCatalog/ClassroomPlaybackSurface")
  .then(module => ({ default: module.ClassroomPlaybackSurface })));

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onPreviewStateChange?: (open: boolean) => void;
};

const StudioPanel: FC<Props> = ({ collapsed, onToggleCollapsed, courseId, workspaceScope, onPreviewStateChange }) => {
  const { user } = useAuthSession();
  const draftEntry = useDraftPreview(state => state.entry);
  const conversationId = useStore(state => state.currentConversationId);
  const outcome = draftEntry?.owner === user?.username && draftEntry?.courseId === courseId && draftEntry?.conversationId === conversationId ? draftEntry.outcome : null;
  const draft = outcome?.draft;
  const selectedDocs = useStore((state) => state.selectedDocs);
  const [allowedTools, setAllowedTools] = useState<GenerationToolId[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [preview, setPreview] = useState<GenerationResultTarget | null>(null);
  const [material, setMaterial] = useState<CourseMaterial | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const [previewRetry, setPreviewRetry] = useState(0);
  const activePreview = preview?.courseId === courseId ? preview : null;
  const previewOpen = Boolean(activePreview) && !collapsed;

  useEffect(() => { setPreview(null); }, [courseId, user?.username]);
  useEffect(() => {
    const ref = draft?.reference || (outcome?.status === 'completed' || outcome?.status === 'discarded' ? outcome.artifact_reference : null);
    if (ref) setPreview({courseId: ref.source_course_id, materialType: ref.artifact_type, materialId: ref.artifact_id, title: ref.title || '文档'});
  }, [draft, outcome]);
  useEffect(() => {
    onPreviewStateChange?.(previewOpen);
    return () => onPreviewStateChange?.(false);
  }, [previewOpen, onPreviewStateChange]);
  useEffect(() => {
    let cancelled = false;
    setMaterial(null);
    setPreviewError(false);
    if (activePreview && activePreview.materialType !== "classroom") {
      void getCourseMaterial(activePreview.courseId, activePreview.materialType, activePreview.materialId)
        .then((result) => { if (!cancelled) setMaterial(result); })
        .catch(() => { if (!cancelled) setPreviewError(true); });
    }
    return () => { cancelled = true; };
  }, [activePreview, previewRetry]);

  useEffect(() => {
    let cancelled = false;
    setCatalogError(null);
    setCatalogLoading(true);
    void getGenerationTools()
      .then((tools) => { if (!cancelled) setAllowedTools(tools); })
      .catch((reason) => {
        if (!cancelled) {
          setAllowedTools([]);
          setCatalogError(reason instanceof Error ? reason.message : "生成工具加载失败");
        }
      })
      .finally(() => { if (!cancelled) setCatalogLoading(false); });
    return () => { cancelled = true; };
  }, [reloadKey]);

  const referenceIntent = material ? createRevisionIntent(material, user?.username || "") : null;

  if (collapsed) {
    return <button type="button" className="generation-factory-collapsed" onClick={onToggleCollapsed} aria-label="打开生成工厂">生成</button>;
  }
  if (activePreview) {
    return <section className="generation-factory__preview" aria-label="生成文件预览">
      <header>
        <button type="button" onClick={() => setPreview(null)}><MaterialIcon name="arrow_back" />返回生成工厂</button>
        <h2>{activePreview.title}</h2>
      </header>
      <div className="generation-factory__preview-body">
        {draft && draft.reference.artifact_id === activePreview.materialId ? <DraftDocumentPreview draft={draft} busy={draftEntry?.busy || false} /> : activePreview.materialType === "classroom" ? <Suspense fallback={<p role="status">正在打开课堂…</p>}>
          <ClassroomPlaybackSurface courseId={activePreview.courseId} classroomId={activePreview.materialId} mode="manage" kind="personal_classroom" />
        </Suspense> : previewError ? <div role="alert"><p>文件暂时无法加载，请重试。</p><button type="button" onClick={() => setPreviewRetry(value => value + 1)}>重新加载</button></div>
          : !material ? <p role="status">正在打开文件…</p>
          : <CourseMaterialArtifactPreview key={`${material.material_type}:${material.material_id}`} material={material} onReference={referenceIntent ? () => dispatchRevisionIntent(referenceIntent) : undefined} />}
      </div>
    </section>;
  }
  if (catalogError) {
    return <div className="generation-factory__catalog-error" role="alert"><p>{catalogError}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)}>重新加载</button></div>;
  }
  if (catalogLoading) return <div className="generation-factory__catalog-state">正在加载生成工具…</div>;
  return (
    <GenerationFactory
      courseId={courseId}
      scopeType={workspaceScope?.scopeType}
      scopeId={workspaceScope?.scopeId}
      allowedTools={allowedTools}
      selectedDocumentIds={selectedDocs}
      sourceLibraries={["course", "personal"]}
      onOpenResult={setPreview}
      resultHref={({ courseId: targetCourseId, materialType, materialId }) => buildRoleCourseHash(user?.role, "resources", targetCourseId, { material_type: materialType, material_id: materialId })}
    />
  );
};

export default StudioPanel;
