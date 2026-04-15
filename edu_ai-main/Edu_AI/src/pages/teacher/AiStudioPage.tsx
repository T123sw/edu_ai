import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import SourcePanel from '../../components/teacher/SourcePanel';
import ChatPanel from '../../components/teacher/ChatPanel';
import StudioPanel from '../../components/teacher/StudioPanel';
import './AiStudioPage.css';

const COLLAPSED_WIDTH = '72px';
const EXPANDED_WIDTH_FORMULA = 'clamp(320px, 24vw, 520px)';
// 打开知识库预览时，左栏加宽一些（同时仍保持响应式上限，避免挤压中间对话区过多）
const LEFT_PREVIEW_WIDTH_FORMULA = 'clamp(420px, 32vw, 720px)';
// 打开生成工厂预览时，右栏加宽一些
const RIGHT_PREVIEW_WIDTH_FORMULA = 'clamp(420px, 32vw, 720px)';
const CENTER_COLUMN_FORMULA = 'minmax(520px, 1fr)';

export default function AiStudioPage() {
  const { courseId } = useParams();
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);
  const [studioPreviewOpen, setStudioPreviewOpen] = useState(false);

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
            onPreviewStateChange={(open) => setKbPreviewOpen(open)}
          />
        </div>
      </div>

      {/* Center Panel: ChatPanel */}
      <div className="ai-studio-content">
        <div className="ai-panel">
          <ChatPanel courseId={courseId} />
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
            onPreviewStateChange={(open) => setStudioPreviewOpen(open)}
          />
        </div>
      </div>
    </div>
  );
}
