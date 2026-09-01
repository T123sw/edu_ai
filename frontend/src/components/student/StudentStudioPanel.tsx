import { useEffect, useState } from "react";

import { getGenerationTools } from "../../stitch/api/generationTools";
import type { GenerationToolId } from "../../stitch/shared/generation/generationCatalog";
import { StudentGenerationFactory } from "../../stitch/student/tools/StudentGenerationFactory";
import { MaterialIcon } from "../../stitch/shared";

export default function StudentStudioPanel({
  courseId,
  selectedDocumentIds,
  collapsed = false,
  onToggleCollapsed,
}: {
  courseId: string;
  selectedDocumentIds: readonly string[];
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}) {
  const [tools, setTools] = useState<GenerationToolId[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getGenerationTools()
      .then((result) => { if (!cancelled) setTools(result); })
      .catch((reason) => { if (!cancelled) { setTools([]); setError(reason instanceof Error ? reason.message : "生成工具加载失败"); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reloadKey]);

  if (collapsed) return <button type="button" className="student-ai__collapsed-panel" onClick={onToggleCollapsed}><MaterialIcon name="auto_awesome" /><span>生成工具</span></button>;
  return (
    <section className="student-studio-panel" aria-label="学生生成工具">
      <div className="student-studio-panel__top">{onToggleCollapsed ? <button aria-label="收起生成工具" onClick={onToggleCollapsed}><MaterialIcon name="chevron_right" /></button> : null}</div>
      {loading ? <div className="student-studio-panel__state">正在加载生成工具…</div> : null}
      {error ? <div className="student-studio-panel__state is-error"><p>{error}</p><button onClick={() => setReloadKey((value) => value + 1)}>重新加载</button></div> : null}
      {!loading && !error ? <StudentGenerationFactory courseId={courseId} allowedTools={tools} selectedDocumentIds={selectedDocumentIds} /> : null}
    </section>
  );
}
