import { useEffect, useMemo, useState } from "react";
import SourcePanel from "../../components/teacher/SourcePanel";
import ChatPanel from "../../components/teacher/ChatPanel";
import StudioPanel from "../../components/teacher/StudioPanel";
import "../../pages/teacher/AiStudioPage.css";
import { useStore } from "../../store/teacher/useStore";
import {
  AppSurface,
  MaterialIcon,
  SidebarBackLink,
  SidebarDock,
  SidebarNav,
  routeHref,
  routes,
  useAppShell,
} from "../shared";
import {
  getWorkspaceScopeLabel,
  normalizeWorkspaceScope,
  readWorkspaceScopeFromSearch,
  writeWorkspaceScopeToSearch,
  type WorkspaceScope,
} from "../../services/teacher/workspaceScope";
import {
  getAiStudioGridTemplate,
  resolveCompactPanelState,
} from "../../pages/teacher/aiStudioLayout";
import { useAiStudioLayout } from "../../pages/teacher/useAiStudioLayout";

function getHashSearchParams(hash = window.location.hash): URLSearchParams {
  const normalized = hash.replace(/^#/, "");
  const queryStart = normalized.indexOf("?");
  return new URLSearchParams(queryStart >= 0 ? normalized.slice(queryStart + 1) : "");
}

function writeAiWorkspaceHash(scope: WorkspaceScope) {
  const nextSearch = writeWorkspaceScopeToSearch(getHashSearchParams(), scope);
  window.location.hash = `${routes.ai}?${nextSearch.toString()}`;
}

export function AIWorkspacePage() {
  const { selectedCourse } = useAppShell();
  const statusCard = useStore((state) => state.statusCard);
  const [hash, setHash] = useState(() => window.location.hash);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);
  const [studioPreviewOpen, setStudioPreviewOpen] = useState(false);
  const [drawerPanel, setDrawerPanel] = useState<"source" | "studio" | null>(null);
  const { workspaceRef, layoutMode } = useAiStudioLayout<HTMLDivElement>();

  const courseLabel = selectedCourse?.title?.trim() || "未指定课程";
  const workspaceScope = useMemo(() => {
    const current = readWorkspaceScopeFromSearch(getHashSearchParams(hash));
    const firstTopic = Array.isArray(statusCard?.topics)
      ? statusCard.topics.map((item) => String(item || "").trim()).find(Boolean)
      : "";

    return normalizeWorkspaceScope({
      ...current,
      scopeLabel: current.scopeLabel || (current.scopeType === "knowledge_point" ? firstTopic : "课程总目录"),
    });
  }, [hash, statusCard]);
  const knowledgePointLabel = getWorkspaceScopeLabel(workspaceScope);

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    if (layoutMode !== "drawer") {
      setDrawerPanel(null);
    }
  }, [layoutMode]);

  const pageStyle = useMemo<React.CSSProperties>(() => {
    const effectiveState =
      layoutMode === "compact"
        ? resolveCompactPanelState({ leftCollapsed, rightCollapsed })
        : { leftCollapsed, rightCollapsed };

    return {
      gridTemplateColumns: getAiStudioGridTemplate({
        mode: layoutMode,
        ...effectiveState,
        leftPreviewOpen: kbPreviewOpen,
        rightPreviewOpen: studioPreviewOpen,
      }),
      transition: "grid-template-columns 0.2s ease-in-out",
    };
  }, [kbPreviewOpen, layoutMode, leftCollapsed, rightCollapsed, studioPreviewOpen]);

  const effectivePanelState =
    layoutMode === "compact"
      ? resolveCompactPanelState({ leftCollapsed, rightCollapsed })
      : { leftCollapsed, rightCollapsed };

  const toggleLeftPanel = () => {
    if (layoutMode === "drawer") {
      setDrawerPanel((current) => current === "source" ? null : "source");
      return;
    }
    if (effectivePanelState.leftCollapsed) {
      setLeftCollapsed(false);
      if (layoutMode === "compact") setRightCollapsed(true);
    } else {
      setLeftCollapsed(true);
      setKbPreviewOpen(false);
    }
  };

  const toggleRightPanel = () => {
    if (layoutMode === "drawer") {
      setDrawerPanel((current) => current === "studio" ? null : "studio");
      return;
    }
    if (effectivePanelState.rightCollapsed) {
      setRightCollapsed(false);
      if (layoutMode === "compact") setLeftCollapsed(true);
    } else {
      setRightCollapsed(true);
      setStudioPreviewOpen(false);
    }
  };

  return (
    <AppSurface className="ai-workspace-shell flex min-h-screen">
      <SidebarDock className="ai-workspace-shell__sidebar h-screen px-5 py-6">
        <div className="mb-6">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-(--accent-strong)">
            {courseLabel}
          </h1>
          <p className="mt-1 text-sm text-(--muted-text)">教师 AI 工作台</p>
        </div>
        <SidebarNav activeRoute={routes.ai} />
      </SidebarDock>

      <main className="ai-workspace-shell__main flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
        <section className="ai-studio-context-bar ai-workspace-shell__context" aria-label="当前问答上下文">
          <div className="ai-studio-context-bar__scope">
            <div className="ai-studio-context-bar__item">
              <span className="ai-studio-context-bar__label">当前课程</span>
              <span className="ai-studio-context-bar__value" title={courseLabel}>
                {courseLabel}
              </span>
            </div>

            <span className="ai-studio-context-bar__divider" aria-hidden="true" />

            <div className="ai-studio-context-bar__item">
              <span className="ai-studio-context-bar__label">当前知识点</span>
              <span className="ai-studio-context-bar__value" title={knowledgePointLabel}>
                {knowledgePointLabel}
              </span>
            </div>
          </div>

          <div className="ai-studio-context-bar__actions" aria-label="全局操作">
            <a
              href={routeHref(routes.profile)}
              className="ai-studio-profile-entry"
              aria-label="进入个人中心"
            >
              <span className="ai-studio-profile-entry__icon">
                <MaterialIcon name="person" />
              </span>
              <span>个人中心</span>
            </a>
          </div>
        </section>

        <div className="ai-workspace-shell__frame">
          <div
            ref={workspaceRef}
            className={`ai-studio-page workspace-ai-studio-page h-full min-h-0 ai-studio-page--${layoutMode}`}
            style={pageStyle}
          >
            {layoutMode === "drawer" && (
              <>
                <div className="ai-studio-panel-switcher" aria-label="工作台面板切换">
                  <button
                    type="button"
                    aria-pressed={drawerPanel === "source"}
                    onClick={toggleLeftPanel}
                  >
                    知识库
                  </button>
                  <button
                    type="button"
                    aria-pressed={drawerPanel === "studio"}
                    onClick={toggleRightPanel}
                  >
                    生成工厂
                  </button>
                </div>
                {drawerPanel && (
                  <button
                    type="button"
                    className="ai-studio-drawer-backdrop"
                    aria-label="关闭侧边面板"
                    onClick={() => setDrawerPanel(null)}
                  />
                )}
              </>
            )}

            <div className={`ai-studio-sider ai-studio-sider--left${drawerPanel === "source" ? " is-open" : ""}`}>
              <div className="ai-panel">
                <SourcePanel
                  collapsed={layoutMode === "drawer" ? false : effectivePanelState.leftCollapsed}
                  onToggleCollapsed={toggleLeftPanel}
                  courseId={selectedCourse?.id}
                  workspaceScope={workspaceScope}
                  onPreviewStateChange={(open) => setKbPreviewOpen(open)}
                />
              </div>
            </div>

            <div className="ai-studio-content">
              <div className="ai-panel">
                <ChatPanel
                  courseId={selectedCourse?.id}
                  workspaceScope={workspaceScope}
                  onWorkspaceScopeChange={(nextScope) => {
                    writeAiWorkspaceHash(nextScope);
                  }}
                />
              </div>
            </div>

            <div className={`ai-studio-sider ai-studio-sider--right${drawerPanel === "studio" ? " is-open" : ""}`}>
              <div className="ai-panel">
                <StudioPanel
                  collapsed={layoutMode === "drawer" ? false : effectivePanelState.rightCollapsed}
                  onToggleCollapsed={toggleRightPanel}
                  courseId={selectedCourse?.id}
                  workspaceScope={workspaceScope}
                  onPreviewStateChange={(open) => setStudioPreviewOpen(open)}
                />
              </div>
            </div>
          </div>
        </div>
      </main>
    </AppSurface>
  );
}

export { AIWorkspacePage as WorkspaceOverviewPage };
