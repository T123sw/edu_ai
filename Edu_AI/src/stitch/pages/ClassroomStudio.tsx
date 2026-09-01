import { useCallback, useEffect, useMemo, useState } from "react";
import { listClassrooms } from "../api/classroom";
import { getClassroomCatalog } from "../api/classroomCatalog";
import type { ClassroomCatalog, ClassroomMaterial } from "../api/types";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { LearningResourceGenerationPanel } from "../course/knowledge/LearningResourceGenerationPanel";
import { CourseResourceViewer } from "../course/classroomCatalog/CourseResourceViewer";
import { ClassroomWorkspaceLayout } from "../course/classroomCatalog/ClassroomWorkspaceLayout";
import { buildWorkspaceHash, readWorkspaceTarget, type ClassroomWorkspaceTarget } from "../course/classroomCatalog/classroomWorkspaceTarget";
import { CurriculumNodeOverview } from "../course/classroomCatalog/CurriculumNodeOverview";
import { CurriculumResourceTree } from "../course/classroomCatalog/CurriculumResourceTree";
import { MyClassroomList } from "../course/classroomCatalog/MyClassroomList";
import { presentMyClassrooms } from "../course/classroomCatalog/myClassroomPresentation";
import { buildCurriculumResourceTree, filterCurriculumTree, type CurriculumTreeNode } from "../course/classroomCatalog/catalogPresentation";
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
  const [personalClassrooms, setPersonalClassrooms] = useState<ClassroomMaterial[]>([]);
  const [personalLoading, setPersonalLoading] = useState(true);
  const [personalError, setPersonalError] = useState<string | null>(null);
  const [personalReloadToken, setPersonalReloadToken] = useState(0);
  const [query, setQuery] = useState("");
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [selectedPersonalClassroomId, setSelectedPersonalClassroomId] = useState<string | null>(() => {
    const target = readWorkspaceTarget(window.location.hash);
    return target.kind === "personal_classroom" ? target.classroomId : null;
  });
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

  useEffect(() => {
    if (!courseId) { setPersonalClassrooms([]); setPersonalLoading(false); return; }
    let cancelled = false;
    setPersonalLoading(true); setPersonalError(null);
    listClassrooms(courseId, "mine")
      .then((value) => { if (!cancelled) setPersonalClassrooms(value); })
      .catch((reason) => { if (!cancelled) setPersonalError(reason instanceof Error ? reason.message : "个人课堂加载失败"); })
      .finally(() => { if (!cancelled) setPersonalLoading(false); });
    return () => { cancelled = true; };
  }, [courseId, personalReloadToken]);

  const tree = useMemo(() => buildCurriculumResourceTree(catalog?.leaves ?? []), [catalog?.leaves]);
  const filteredTree = useMemo(() => filterCurriculumTree(tree, query), [query, tree]);
  const myClassroomItems = useMemo(() => presentMyClassrooms(personalClassrooms), [personalClassrooms]);

  useEffect(() => {
    if (!catalog || !tree.length) return;
    const target = readWorkspaceTarget(window.location.hash);
    if (target.kind === "personal_classroom") {
      setSelectedNodeId(null); setSelectedResourceId(null);
      return;
    }
    const leaf = catalog.leaves.find((item) => item.leaf_id === target.nodeId);
    const resource = target.kind === "catalog_resource"
      ? leaf?.resources.find((item) => item.material_id === target.resourceId)
      : null;
    if (leaf) {
      setSelectedNodeId(leaf.leaf_id); setSelectedResourceId(resource?.material_id ?? null);
      setOpenKeys((current) => new Set([...current, ...ancestorKeys(tree, leaf.leaf_id)]));
    } else setOpenKeys((current) => current.size ? current : new Set([tree[0].key]));
  }, [catalog, tree]);

  const selectedLeaf = catalog?.leaves.find((leaf) => leaf.leaf_id === selectedNodeId) ?? null;
  const selectedResource = selectedLeaf?.resources.find((resource) => resource.material_id === selectedResourceId) ?? null;
  const selectedPersonalClassroom = myClassroomItems.find((item) => item.id === selectedPersonalClassroomId) ?? null;
  const effectiveOpenKeys = useMemo(() => {
    if (!query.trim()) return openKeys;
    const keys = new Set(openKeys);
    const collect = (nodes: CurriculumTreeNode[]) => nodes.forEach((node) => { if (node.kind === "branch") keys.add(node.key); collect(node.children); });
    collect(filteredTree); return keys;
  }, [filteredTree, openKeys, query]);

  const updateLocation = (target: ClassroomWorkspaceTarget) => {
    if (!courseId || !catalog) return;
    window.history.replaceState(null, "", buildWorkspaceHash(catalog.mode === "learn" ? "student" : "teacher", courseId, target));
  };
  const selectNode = (nodeId: string) => {
    setSelectedPersonalClassroomId(null); setSelectedNodeId(nodeId); setSelectedResourceId(null); setDrawerOpen(false);
    updateLocation({ kind: "overview", nodeId });
  };
  const selectResource = (nodeId: string, resourceId: string) => {
    setSelectedPersonalClassroomId(null); setSelectedNodeId(nodeId); setSelectedResourceId(resourceId); setDrawerOpen(false);
    updateLocation({ kind: "catalog_resource", nodeId, resourceId });
  };
  const selectPersonalClassroom = (classroomId: string) => {
    setSelectedNodeId(null); setSelectedResourceId(null); setSelectedPersonalClassroomId(classroomId); setDrawerOpen(false);
    updateLocation({ kind: "personal_classroom", classroomId });
  };

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
      : catalog ? <ClassroomWorkspaceLayout
        directoryOpen={drawerOpen}
        qaOpen={false}
        onCloseDirectory={() => setDrawerOpen(false)}
        onCloseQa={() => undefined}
        directory={<div className="course-classroom-catalog__directory">
          <div className="course-classroom-catalog__directory-heading"><div><strong>课程目录</strong><small> · {catalog.leaves.length} 个小节</small></div><button type="button" className="catalog-drawer-close" aria-label="关闭课程目录" onClick={() => setDrawerOpen(false)}><MaterialIcon name="close" /></button></div>
          <div className="course-classroom-catalog__directory-tree">
            <CurriculumResourceTree nodes={filteredTree} selectedNodeId={selectedNodeId} selectedResourceId={selectedResourceId} openKeys={effectiveOpenKeys}
              onToggle={(key) => setOpenKeys((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; })}
              onSelectNode={selectNode} onSelectResource={selectResource} />
          </div>
          <MyClassroomList items={myClassroomItems} loading={personalLoading} error={personalError} selectedId={selectedPersonalClassroomId}
            onSelect={selectPersonalClassroom} onRetry={() => setPersonalReloadToken((value) => value + 1)} />
        </div>}
        viewer={<section className="course-classroom-catalog__content">
          {selectedPersonalClassroom ? <div className="personal-classroom-placeholder">
            <MaterialIcon name="smart_display" /><p>个人 AI 课堂</p><h2>{selectedPersonalClassroom.title}</h2><span>可观看</span>
          </div> : <>
            {selectedLeaf ? <p className="course-classroom-catalog__breadcrumb">{selectedLeaf.path_titles.join(" / ")}</p> : null}
            {selectedResource && selectedLeaf ? <CourseResourceViewer courseId={courseId} nodeId={selectedLeaf.leaf_id} resource={selectedResource} mode={catalog.mode} onChanged={reload} />
              : <CurriculumNodeOverview leaf={selectedLeaf} mode={catalog.mode} totalLeafCount={catalog.leaves.length} onGenerate={() => setGenerationOpen(true)} onSelectResource={(resourceId) => selectedLeaf && selectResource(selectedLeaf.leaf_id, resourceId)} />}
          </>}
        </section>}
        qa={<div className="course-classroom-workspace__qa-empty"><MaterialIcon name="forum" /><strong>当前内容问答</strong><p>选择一份学习资料后，即可围绕当前内容提问。</p></div>}
      /> : null}
    {generationOpen ? <LearningResourceGenerationPanel onClose={() => { setGenerationOpen(false); reload(); }} /> : null}
  </main></AppSurface>;
}
