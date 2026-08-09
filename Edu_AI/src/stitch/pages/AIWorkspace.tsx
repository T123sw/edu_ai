import { useEffect, useMemo, useState } from "react";
import SourcePanel from "../../components/teacher/SourcePanel";
import ChatPanel from "../../components/teacher/ChatPanel";
import StudioPanel from "../../components/teacher/StudioPanel";
import "../../pages/teacher/AiStudioPage.css";
import { useStore } from "../../store/teacher/useStore";
import {
  AppSurface,
  routes,
  useAppShell,
} from "../shared";
import {
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
import { useAuthSession } from "../authSession";

function getHashSearchParams(hash = window.location.hash): URLSearchParams {
  const normalized = hash.replace(/^#/, "");
  const queryStart = normalized.indexOf("?");
  return new URLSearchParams(queryStart >= 0 ? normalized.slice(queryStart + 1) : "");
}

function writeAiWorkspaceHash(scope: WorkspaceScope, isStudent: boolean) {
  const nextSearch = writeWorkspaceScopeToSearch(getHashSearchParams(), scope);
  window.location.hash = `${isStudent ? "student-ai" : routes.ai}?${nextSearch.toString()}`;
}

export function AIWorkspacePage() {
  const { user } = useAuthSession();
  const { selectedCourse } = useAppShell();
  const statusCard = useStore((state) => state.statusCard);
  const [hash, setHash] = useState(() => window.location.hash);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);
  const [studioPreviewOpen, setStudioPreviewOpen] = useState(false);
  const [drawerPanel, setDrawerPanel] = useState<"source" | "studio" | null>(null);
  const { workspaceRef, layoutMode } = useAiStudioLayout<HTMLDivElement>();

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
    <AppSurface className="ai-workspace-shell h-[calc(100vh-var(--course-header-height))] overflow-hidden">
      <main className="ai-workspace-shell__main flex h-full min-h-0 flex-1 flex-col overflow-hidden">
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
                    writeAiWorkspaceHash(nextScope, user?.role === "student");
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
