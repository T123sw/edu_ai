import React, { useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import SourcePanel from '../../components/teacher/SourcePanel';
import ChatPanel from '../../components/teacher/ChatPanel';
import StudioPanel from '../../components/teacher/StudioPanel';
import { useCourseStore } from '../../store/course/useCourseStore';
import { useStore } from '../../store/teacher/useStore';
import { getAiStudioCourseLabel } from './aiStudioContext';
import {
  getWorkspaceScopeLabel,
  normalizeWorkspaceScope,
  readWorkspaceScopeFromSearch,
  writeWorkspaceScopeToSearch,
} from '../../services/teacher/workspaceScope';
import '../../features/ai-workspace/AIWorkspacePage.css';

const COLLAPSED_WIDTH = '72px';
const EXPANDED_WIDTH_FORMULA = 'clamp(320px, 24vw, 520px)';
// 打开知识库预览时，左栏加宽一些（同时仍保持响应式上限，避免挤压中间对话区过多）
const LEFT_PREVIEW_WIDTH_FORMULA = 'clamp(420px, 32vw, 720px)';
// 打开生成工厂预览时，右栏加宽一些
const RIGHT_PREVIEW_WIDTH_FORMULA = 'clamp(420px, 32vw, 720px)';
const CENTER_COLUMN_FORMULA = 'minmax(520px, 1fr)';

export default function AiStudioPage() {
  const { courseId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentCourse = useCourseStore((state) => state.currentCourse);
  const statusCard = useStore((state) => state.statusCard);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);
  const [studioPreviewOpen, setStudioPreviewOpen] = useState(false);
  const courseLabel = getAiStudioCourseLabel(currentCourse, courseId);
  const workspaceScope = useMemo(() => {
    const current = readWorkspaceScopeFromSearch(searchParams);
    const firstTopic = Array.isArray(statusCard?.topics)
      ? statusCard.topics.map((item) => String(item || '').trim()).find(Boolean)
      : '';

    return normalizeWorkspaceScope({
      ...current,
      scopeLabel: current.scopeLabel || (current.scopeType === 'knowledge_point' ? firstTopic : '课程总目录'),
    });
  }, [searchParams, statusCard]);
  const knowledgePointLabel = getWorkspaceScopeLabel(workspaceScope);

  // 动态计算 grid 布局，当侧边栏折叠时，中间对话区自动扩大
  const pageStyle = useMemo<React.CSSProperties>(() => {
    // 左栏：折叠时 72px，预览时用更宽的 LEFT_PREVIEW_WIDTH_FORMULA，否则用默认 EXPANDED_WIDTH_FORMULA
    const leftColumn = leftCollapsed 
      ? COLLAPSED_WIDTH 
      : (kbPreviewOpen ? LEFT_PREVIEW_WIDTH_FORMULA : EXPANDED_WIDTH_FORMULA);
    
    // 右栏：折叠时 72px，预览时用更宽的 RIGHT_PREVIEW_WIDTH_FORMULA，否则用默认 EXPANDED_WIDTH_FORMULA
    const rightColumn = rightCollapsed 
      ? COLLAPSED_WIDTH 
      : (studioPreviewOpen ? RIGHT_PREVIEW_WIDTH_FORMULA : EXPANDED_WIDTH_FORMULA);

    return {
      gridTemplateColumns: `${leftColumn} ${CENTER_COLUMN_FORMULA} ${rightColumn}`,
      transition: 'grid-template-columns 0.2s ease-in-out',
    };
  }, [leftCollapsed, rightCollapsed, kbPreviewOpen, studioPreviewOpen]);

  return (
    <div className="ai-studio-shell workspace-ai-studio-page">
      <section className="ai-studio-context-bar" aria-label="当前问答上下文">
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

      <div className="ai-studio-page" style={pageStyle}>
        {/* Left Panel: SourcePanel */}
        <div className="ai-studio-sider">
          <div className="ai-panel">
            <SourcePanel
              collapsed={leftCollapsed}
              onToggleCollapsed={() => {
                setLeftCollapsed((v) => !v);
                if (!leftCollapsed) setKbPreviewOpen(false);
              }}
              courseId={courseId}
              workspaceScope={workspaceScope}
              onPreviewStateChange={(open) => setKbPreviewOpen(open)}
            />
          </div>
        </div>

        {/* Center Panel: ChatPanel */}
        <div className="ai-studio-content">
          <div className="ai-panel">
            <ChatPanel
              courseId={courseId}
              workspaceScope={workspaceScope}
              onWorkspaceScopeChange={(nextScope) => {
                setSearchParams(writeWorkspaceScopeToSearch(searchParams, nextScope));
              }}
            />
          </div>
        </div>

        {/* Right Panel: StudioPanel */}
        <div className="ai-studio-sider">
          <div className="ai-panel">
            <StudioPanel
              collapsed={rightCollapsed}
              onToggleCollapsed={() => {
                setRightCollapsed((v) => !v);
                if (!rightCollapsed) setStudioPreviewOpen(false);
              }}
              courseId={courseId}
              workspaceScope={workspaceScope}
              onPreviewStateChange={(open) => setStudioPreviewOpen(open)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
