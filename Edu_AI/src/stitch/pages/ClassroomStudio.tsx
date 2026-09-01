import { useCallback, useEffect, useMemo, useState } from "react";
import { getClassroomCatalog } from "../api/classroomCatalog";
import type { ClassroomCatalog } from "../api/types";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { LearningResourceGenerationPanel } from "../course/knowledge/LearningResourceGenerationPanel";
import { CourseResourceViewer } from "../course/classroomCatalog/CourseResourceViewer";
import { CurriculumNodeOverview } from "../course/classroomCatalog/CurriculumNodeOverview";
import { CurriculumResourceTree } from "../course/classroomCatalog/CurriculumResourceTree";
import { buildCatalogHash, buildCurriculumResourceTree, filterCurriculumTree, readCatalogTarget, type CurriculumTreeNode } from "../course/classroomCatalog/catalogPresentation";
import "../course/classroomCatalog/courseClassroomCatalog.css";
import { AppSurface, MaterialIcon } from "../shared";
export { classroomPageDefinition } from "./classroomPageDefinition";

function ancestorKeys(nodes: CurriculumTreeNode[], leafId: string): string[] {
  for (const node of nodes) {
    if (node.leaf?.leaf_id === leafId) return [node.key];
    const nested = ancestorKeys(node.children, leafId);
    if (nested.length) return [node.key, ...nested];
  }
  return [];
}

export function ClassroomStudioPage() {
  const { courseId } = useCourseRoute();
  const [catalog, setCatalog] = useState<ClassroomCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [query, setQuery] = useState("");
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [generationOpen, setGenerationOpen] = useState(false);
  const reload = useCallback(() => setReloadToken((value) => value + 1), []);

  useEffect(() => {
    if (!courseId) { setCatalog(null); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError(null);
    getClassroomCatalog(courseId)
      .then((value) => { if (!cancelled) setCatalog(value); })
      .catch((reason) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "课程目录加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, reloadToken]);

  const tree = useMemo(() => buildCurriculumResourceTree(catalog?.leaves ?? []), [catalog?.leaves]);
  const filteredTree = useMemo(() => filterCurriculumTree(tree, query), [query, tree]);

  useEffect(() => {
    if (!catalog || !tree.length) return;
    const target = readCatalogTarget(window.location.hash);
    const leaf = catalog.leaves.find((item) => item.leaf_id === target.nodeId);
    const resource = leaf?.resources.find((item) => item.material_id === target.resourceId);
    if (leaf) {
      setSelectedNodeId(leaf.leaf_id); setSelectedResourceId(resource?.material_id ?? null);
      setOpenKeys((current) => new Set([...current, ...ancestorKeys(tree, leaf.leaf_id)]));
    } else setOpenKeys((current) => current.size ? current : new Set([tree[0].key]));
  }, [catalog, tree]);

  const selectedLeaf = catalog?.leaves.find((leaf) => leaf.leaf_id === selectedNodeId) ?? null;
  const selectedResource = selectedLeaf?.resources.find((resource) => resource.material_id === selectedResourceId) ?? null;
  const effectiveOpenKeys = useMemo(() => {
    if (!query.trim()) return openKeys;
    const keys = new Set(openKeys);
    const collect = (nodes: CurriculumTreeNode[]) => nodes.forEach((node) => { if (node.kind === "branch") keys.add(node.key); collect(node.children); });
    collect(filteredTree); return keys;
  }, [filteredTree, openKeys, query]);

  const updateLocation = (nodeId: string | null, resourceId: string | null) => {
    if (!courseId || !catalog) return;
    window.history.replaceState(null, "", buildCatalogHash(catalog.mode === "learn" ? "student" : "teacher", courseId, nodeId, resourceId));
  };
  const selectNode = (nodeId: string) => { setSelectedNodeId(nodeId); setSelectedResourceId(null); setDrawerOpen(false); updateLocation(nodeId, null); };
  const selectResource = (nodeId: string, resourceId: string) => { setSelectedNodeId(nodeId); setSelectedResourceId(resourceId); setDrawerOpen(false); updateLocation(nodeId, resourceId); };

  if (!courseId) return <AppSurface><main className="course-classroom-catalog"><p>请先选择一门课程。</p></main></AppSurface>;
  return <AppSurface><main className="course-classroom-catalog">
    <header className="course-classroom-catalog__toolbar"><div><p>课程学习资源</p><h1>AI 课堂</h1></div>
      <div className="course-classroom-catalog__tools">
        <button type="button" className="catalog-directory-toggle" onClick={() => setDrawerOpen(true)}><MaterialIcon name="menu_book" />课程目录</button>
        <label className="course-classroom-catalog__search"><MaterialIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="搜索课程目录" placeholder="搜索章节、小节或资料" /></label>
        {catalog?.mode === "manage" ? <button type="button" className="catalog-primary-action" onClick={() => setGenerationOpen(true)}><MaterialIcon name="auto_awesome" />生成学习资源</button> : null}
      </div>
    </header>
    {loading ? <div className="course-classroom-catalog__layout catalog-loading" aria-label="正在加载课程目录"><span /><span /></div>
      : error ? <section className="catalog-retry"><div><h2>课程目录暂时无法加载</h2><p>{error}</p><button type="button" onClick={reload}>重新加载</button></div></section>
      : catalog ? <div className="course-classroom-catalog__layout">
        {drawerOpen ? <button type="button" className="catalog-drawer-scrim" aria-label="关闭课程目录" onClick={() => setDrawerOpen(false)} /> : null}
        <aside className={`course-classroom-catalog__directory${drawerOpen ? " is-open" : ""}`}>
          <div className="course-classroom-catalog__directory-heading"><div><strong>课程目录</strong><small> · {catalog.leaves.length} 个小节</small></div><button type="button" className="catalog-drawer-close" aria-label="关闭课程目录" onClick={() => setDrawerOpen(false)}><MaterialIcon name="close" /></button></div>
          <CurriculumResourceTree nodes={filteredTree} selectedNodeId={selectedNodeId} selectedResourceId={selectedResourceId} openKeys={effectiveOpenKeys}
            onToggle={(key) => setOpenKeys((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; })}
            onSelectNode={selectNode} onSelectResource={selectResource} />
        </aside>
        <section className="course-classroom-catalog__content">
          {selectedLeaf ? <p className="course-classroom-catalog__breadcrumb">{selectedLeaf.path_titles.join(" / ")}</p> : null}
          {selectedResource && selectedLeaf ? <CourseResourceViewer courseId={courseId} nodeId={selectedLeaf.leaf_id} resource={selectedResource} mode={catalog.mode} onChanged={reload} />
            : <CurriculumNodeOverview leaf={selectedLeaf} mode={catalog.mode} totalLeafCount={catalog.leaves.length} onGenerate={() => setGenerationOpen(true)} onSelectResource={(resourceId) => selectedLeaf && selectResource(selectedLeaf.leaf_id, resourceId)} />}
        </section>
      </div> : null}
    {generationOpen ? <LearningResourceGenerationPanel onClose={() => { setGenerationOpen(false); reload(); }} /> : null}
  </main></AppSurface>;
}
