import { useMemo, useState } from "react";
import SourcePanel from "../../components/teacher/SourcePanel";
import ChatPanel from "../../components/teacher/ChatPanel";
import StudioPanel from "../../components/teacher/StudioPanel";
import "../../pages/teacher/AiStudioPage.css";
import { AppSurface, MaterialIcon, SidebarBackLink, SidebarDock, SidebarNav, routes, useAppShell } from "../shared";

const COLLAPSED_WIDTH = "72px";
const EXPANDED_WIDTH_FORMULA = "clamp(320px, 24vw, 520px)";
const LEFT_PREVIEW_WIDTH_FORMULA = "clamp(420px, 32vw, 720px)";
const RIGHT_PREVIEW_WIDTH_FORMULA = "clamp(420px, 32vw, 720px)";
const CENTER_COLUMN_FORMULA = "minmax(520px, 1fr)";

export function AIWorkspacePage() {
  const { selectedCourse } = useAppShell();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);
  const [studioPreviewOpen, setStudioPreviewOpen] = useState(false);

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
    <AppSurface className="flex min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(234,241,255,0.92),transparent_22%),radial-gradient(circle_at_top_right,rgba(191,211,255,0.36),transparent_18%),linear-gradient(180deg,#f8fbff_0%,#f2f6fb_100%)]">
      <SidebarDock className="h-screen bg-[linear-gradient(180deg,rgba(253,254,254,0.96)_0%,rgba(245,248,255,0.94)_100%)] px-5 py-6">
        <div className="mb-6">
          <SidebarBackLink />
          <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">
            {selectedCourse?.title ?? "当前课程"}
          </h1>
          <p className="mt-1 text-sm text-[var(--muted-text)]">教师 AI 工作台</p>
        </div>
        <SidebarNav activeRoute={routes.ai} />
      </SidebarDock>

      <main className="flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-40 border-b border-[var(--shell-border)] bg-[var(--app-bg)]/88 px-6 py-4 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[var(--accent-border)] bg-[var(--accent-soft)] px-3 py-1 text-[10px] font-black uppercase tracking-[0.22em] text-[var(--accent-strong)] shadow-[0_10px_18px_var(--accent-shadow)]">
                <MaterialIcon name="auto_awesome" />
                Teacher Workspace
              </div>
              <h1 className="mt-3 text-2xl font-black tracking-tight text-[var(--accent-strong)]">
                {selectedCourse?.title ?? "当前课程"} 教师工作区
              </h1>
              <p className="mt-1 text-sm text-[var(--muted-text)]">
                资料区、对话区、生成工场三栏联动，保留原有全部功能。
              </p>
            </div>
            <div className="rounded-[22px] border border-[var(--accent-border)] bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(234,241,255,0.82)_100%)] px-4 py-3 shadow-[0_14px_28px_var(--accent-shadow)]">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[var(--accent-strong)]">Workspace Mode</p>
              <p className="mt-2 text-sm font-semibold text-[var(--app-text)]">Teacher Panels</p>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-hidden px-4 py-4 lg:px-5">
          <div className="h-full overflow-hidden rounded-[34px] border border-[var(--shell-border)] bg-[linear-gradient(180deg,rgba(255,255,255,0.34)_0%,rgba(255,255,255,0.18)_100%)] p-2 shadow-[0_24px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
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
                    onPreviewStateChange={(open) => setKbPreviewOpen(open)}
                  />
                </div>
              </div>

              <div className="ai-studio-content">
                <div className="ai-panel">
                  <ChatPanel courseId={selectedCourse?.id} />
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
                    onPreviewStateChange={(open) => setStudioPreviewOpen(open)}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </AppSurface>
  );
}

export { AIWorkspacePage as WorkspaceOverviewPage };
