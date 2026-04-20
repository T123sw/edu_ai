import { useEffect, useMemo, useState } from "react";
import SourcePanel from "../../components/teacher/SourcePanel";
import ChatPanel from "../../components/teacher/ChatPanel";
import StudioPanel from "../../components/teacher/StudioPanel";
import "../../pages/teacher/AiStudioPage.css";
import { useStore } from "../../store/teacher/useStore";
import { AppSurface, SidebarBackLink, SidebarDock, SidebarNav, routes, useAppShell } from "../shared";
import {
  getWorkspaceScopeLabel,
  normalizeWorkspaceScope,
  readWorkspaceScopeFromSearch,
  writeWorkspaceScopeToSearch,
  type WorkspaceScope,
} from "../../services/teacher/workspaceScope";

const COLLAPSED_WIDTH = "72px";
const EXPANDED_WIDTH_FORMULA = "clamp(320px, 24vw, 520px)";
const LEFT_PREVIEW_WIDTH_FORMULA = "clamp(420px, 32vw, 720px)";
const RIGHT_PREVIEW_WIDTH_FORMULA = "clamp(420px, 32vw, 720px)";
const CENTER_COLUMN_FORMULA = "minmax(520px, 1fr)";

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

  const pageStyle = useMemo<React.CSSProperties>(() => {
    const leftColumn = leftCollapsed
      ? COLLAPSED_WIDTH
      : (kbPreviewOpen ? LEFT_PREVIEW_WIDTH_FORMULA : EXPANDED_WIDTH_FORMULA);

    const rightColumn = rightCollapsed
      ? COLLAPSED_WIDTH
      : (studioPreviewOpen ? RIGHT_PREVIEW_WIDTH_FORMULA : EXPANDED_WIDTH_FORMULA);

    return {
      gridTemplateColumns: `${leftColumn} ${CENTER_COLUMN_FORMULA} ${rightColumn}`,
      transition: "grid-template-columns 0.2s ease-in-out",
    };
  }, [kbPreviewOpen, leftCollapsed, rightCollapsed, studioPreviewOpen]);

  return (
    <AppSurface className="ai-workspace-shell flex min-h-screen">
      <SidebarDock className="ai-workspace-shell__sidebar h-screen px-5 py-6">
        <div className="mb-6">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">
            {courseLabel}
          </h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">教师 AI 工作台</p>
        </div>
        <SidebarNav activeRoute={routes.ai} />
      </SidebarDock>

      <main className="ai-workspace-shell__main flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
        <section className="ai-studio-context-bar ai-workspace-shell__context" aria-label="当前问答上下文">
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
        </section>

        <div className="ai-workspace-shell__frame">
          <div className="ai-studio-page workspace-ai-studio-page h-full min-h-0" style={pageStyle}>
            <div className="ai-studio-sider">
              <div className="ai-panel">
                <SourcePanel
                  collapsed={leftCollapsed}
                  onToggleCollapsed={() => {
                    setLeftCollapsed((current) => !current);
                    if (!leftCollapsed) setKbPreviewOpen(false);
                  }}
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

            <div className="ai-studio-sider">
              <div className="ai-panel">
                <StudioPanel
                  collapsed={rightCollapsed}
                  onToggleCollapsed={() => {
                    setRightCollapsed((current) => !current);
                    if (!rightCollapsed) setStudioPreviewOpen(false);
                  }}
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
