import { useEffect, useState, type FC } from "react";

import type { WorkspaceScope } from "../../services/teacher/workspaceScope";
import { GenerationFactory } from "../generation/GenerationFactory";
import { getGenerationTools } from "../../stitch/api/generationTools";
import type { GenerationToolId } from "../../stitch/shared/generation/generationCatalog";
import { buildTeacherCourseHash } from "../../stitch/teacherRoutes";
import { useStore } from "../../store/teacher/useStore";

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onPreviewStateChange?: (open: boolean) => void;
};

const StudioPanel: FC<Props> = ({ collapsed, onToggleCollapsed, courseId }) => {
  const selectedDocs = useStore((state) => state.selectedDocs);
  const [allowedTools, setAllowedTools] = useState<GenerationToolId[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

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

  if (collapsed) {
    return <button type="button" className="generation-factory-collapsed" onClick={onToggleCollapsed} aria-label="打开生成工厂">生成</button>;
  }
  if (catalogError) {
    return <div className="generation-factory__catalog-error" role="alert"><p>{catalogError}</p><button type="button" onClick={() => setReloadKey((value) => value + 1)}>重新加载</button></div>;
  }
  if (catalogLoading) return <div className="generation-factory__catalog-state">正在加载生成工具…</div>;
  return (
    <GenerationFactory
      courseId={courseId}
      allowedTools={allowedTools}
      selectedDocumentIds={selectedDocs}
      sourceLibraries={["course", "personal"]}
      resultHref={({ courseId: targetCourseId, materialType, materialId }) => buildTeacherCourseHash("resources", targetCourseId, { material_type: materialType, material_id: materialId })}
    />
  );
};

export default StudioPanel;
