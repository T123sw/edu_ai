import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listClassrooms } from "../api/classroom";
import { getClassroomCatalog } from "../api/classroomCatalog";
import type { ClassroomCatalog, ClassroomMaterial } from "../api/types";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { LearningResourceGenerationPanel } from "../course/knowledge/LearningResourceGenerationPanel";
import { CourseResourceViewer } from "../course/classroomCatalog/CourseResourceViewer";
import { ClassroomPlaybackSurface } from "../course/classroomCatalog/ClassroomPlaybackSurface";
import { ClassroomWorkspaceLayout } from "../course/classroomCatalog/ClassroomWorkspaceLayout";
import { buildWorkspaceHash, readWorkspaceTarget, type ClassroomWorkspaceTarget } from "../course/classroomCatalog/classroomWorkspaceTarget";
import { CurriculumNodeOverview } from "../course/classroomCatalog/CurriculumNodeOverview";
import { CurriculumResourceTree } from "../course/classroomCatalog/CurriculumResourceTree";
import { MyClassroomList } from "../course/classroomCatalog/MyClassroomList";
import { ContextualClassroomQaPanel, type WorkspaceQaBinding } from "../course/classroomCatalog/ContextualClassroomQaPanel";
import { presentMyClassrooms } from "../course/classroomCatalog/myClassroomPresentation";
import { buildCurriculumResourceTree, type CurriculumTreeNode } from "../course/classroomCatalog/catalogPresentation";
import {
  describeCatalogResourceQa,
  describeOverviewQa,
  describePersonalClassroomQa,
  registrationToBinding,
  type WorkspaceQaRegistration,
} from "../course/classroomCatalog/workspaceQaBinding";
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
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [selectedPersonalClassroomId, setSelectedPersonalClassroomId] = useState<string | null>(() => {
    const target = readWorkspaceTarget(window.location.hash);
    return target.kind === "personal_classroom" ? target.classroomId : null;
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [qaOpen, setQaOpen] = useState(false);
  const [generationOpen, setGenerationOpen] = useState(false);
  const directoryTriggerRef = useRef<HTMLButtonElement | null>(null);
  const qaTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [qaBinding, setQaBinding] = useState<WorkspaceQaBinding>({ status: "empty" });
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
  const qaTarget = useMemo(() => {
    if (selectedPersonalClassroom) return describePersonalClassroomQa(selectedPersonalClassroom.id, selectedPersonalClassroom.title);
    if (selectedResource && catalog) return describeCatalogResourceQa(selectedResource, catalog.mode);
    return describeOverviewQa();
  }, [catalog, selectedPersonalClassroom, selectedResource]);
  useEffect(() => {
    setQaBinding(qaTarget.status === "empty"
      ? { status: "empty" }
      : { status: "loading", title: qaTarget.title, kindLabel: qaTarget.kindLabel });
  }, [qaTarget.key, qaTarget.status]);
  const handleQaControllerChange = useCallback((targetKey: string, registration: WorkspaceQaRegistration | null) => {
    if (targetKey !== qaTarget.key) return;
    if (registration) {
      setQaBinding(registrationToBinding(registration));
      return;
    }
    if (qaTarget.status === "loading") {
      setQaBinding({ status: "loading", title: qaTarget.title, kindLabel: qaTarget.kindLabel });
    }
  }, [qaTarget.key, qaTarget.status, qaTarget.status === "loading" ? qaTarget.kindLabel : "", qaTarget.status === "loading" ? qaTarget.title : ""]);
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
    <nav className="course-classroom-catalog__mobile-tools" aria-label="课堂侧栏入口">
      <button ref={directoryTriggerRef} type="button" className="catalog-directory-toggle" aria-label="打开课程目录" aria-expanded={drawerOpen} aria-controls="classroom-workspace-directory" onClick={() => { setQaOpen(false); setDrawerOpen(true); }}><MaterialIcon name="menu_book" /></button>
      <button ref={qaTriggerRef} type="button" className="catalog-qa-toggle" aria-label="打开 AI 问答" aria-expanded={qaOpen} aria-controls="classroom-workspace-qa" onClick={() => { setDrawerOpen(false); setQaOpen(true); }}><MaterialIcon name="forum" /></button>
    </nav>
    {loading ? <div className="course-classroom-catalog__layout catalog-loading" aria-label="正在加载课程目录"><span /><span /></div>
      : error ? <section className="catalog-retry"><div><h2>课程目录暂时无法加载</h2><p>{error}</p><button type="button" onClick={reload}>重新加载</button></div></section>
      : catalog ? <ClassroomWorkspaceLayout
        directoryOpen={drawerOpen}
        qaOpen={qaOpen}
        onCloseDirectory={() => setDrawerOpen(false)}
        onCloseQa={() => setQaOpen(false)}
        directoryTriggerRef={directoryTriggerRef}
        qaTriggerRef={qaTriggerRef}
        directory={<div className="course-classroom-catalog__directory">
          <div className="course-classroom-catalog__directory-heading"><div><strong>课程目录</strong><small> · {catalog.leaves.length} 个小节</small></div><button type="button" className="catalog-drawer-close" aria-label="关闭课程目录" onClick={() => setDrawerOpen(false)}><MaterialIcon name="close" /></button></div>
          <div className="course-classroom-catalog__directory-tree">
            <CurriculumResourceTree nodes={tree} selectedNodeId={selectedNodeId} selectedResourceId={selectedResourceId} openKeys={openKeys}
              onToggle={(key) => setOpenKeys((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; })}
              onSelectNode={selectNode} onSelectResource={selectResource} />
          </div>
          <MyClassroomList items={myClassroomItems} loading={personalLoading} error={personalError} selectedId={selectedPersonalClassroomId}
            onSelect={selectPersonalClassroom} onRetry={() => setPersonalReloadToken((value) => value + 1)} />
        </div>}
        viewer={<section className="course-classroom-catalog__content">
          {selectedPersonalClassroom ? <ClassroomPlaybackSurface
            courseId={courseId}
            classroomId={selectedPersonalClassroom.id}
            mode={catalog.mode}
            kind="personal_classroom"
            qaTargetKey={qaTarget.key}
            onQaControllerChange={handleQaControllerChange}
          /> : <>
            {selectedResource && selectedLeaf ? <CourseResourceViewer courseId={courseId} nodeId={selectedLeaf.leaf_id} resource={selectedResource} mode={catalog.mode} onChanged={reload} onQaControllerChange={handleQaControllerChange} />
              : <CurriculumNodeOverview leaf={selectedLeaf} mode={catalog.mode} totalLeafCount={catalog.leaves.length} onGenerate={() => setGenerationOpen(true)} onSelectResource={(resourceId) => selectedLeaf && selectResource(selectedLeaf.leaf_id, resourceId)} />}
          </>}
        </section>}
        qa={<><button type="button" className="catalog-qa-drawer-close" aria-label="关闭 AI 问答" onClick={() => setQaOpen(false)}><MaterialIcon name="close" /></button><ContextualClassroomQaPanel binding={qaBinding} /></>}
      /> : null}
    {generationOpen ? <LearningResourceGenerationPanel onClose={() => { setGenerationOpen(false); reload(); }} /> : null}
  </main></AppSurface>;
}
