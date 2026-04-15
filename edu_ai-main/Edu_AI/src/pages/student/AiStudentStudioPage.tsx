import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import SourcePanel from '../../components/student/SourcePanel';
import ChatPanel from '../../components/student/ChatPanel';
import StudioPanel from '../../components/student/StudioPanel';
import '../teacher/AiStudioPage.css';

const COLLAPSED_WIDTH = '72px';
const LEFT_EXPANDED_WIDTH = 'clamp(280px, 22vw, 420px)';
const LEFT_PREVIEW_WIDTH = 'clamp(420px, 32vw, 720px)';
const RIGHT_EXPANDED_WIDTH = 'clamp(280px, 26vw, 460px)';
const CENTER_COLUMN_WIDTH = 'minmax(520px, 1fr)';

interface AiStudentStudioPageProps {
  courseId?: string;
}

export default function AiStudentStudioPage({ courseId }: AiStudentStudioPageProps) {
  const { courseId: routeCourseId } = useParams();
  const resolvedCourseId = courseId || routeCourseId;
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(true);
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);

  const pageStyle = useMemo<React.CSSProperties>(() => {
    const leftColumn = leftCollapsed
      ? COLLAPSED_WIDTH
      : (kbPreviewOpen ? LEFT_PREVIEW_WIDTH : LEFT_EXPANDED_WIDTH);

    const rightColumn = rightCollapsed ? COLLAPSED_WIDTH : RIGHT_EXPANDED_WIDTH;

    return {
      gridTemplateColumns: `${leftColumn} ${CENTER_COLUMN_WIDTH} ${rightColumn}`,
      transition: 'grid-template-columns 0.2s ease-in-out',
    };
  }, [kbPreviewOpen, leftCollapsed, rightCollapsed]);

  return (
    <div className="ai-studio-page" style={pageStyle}>
      <div className="ai-studio-sider">
        <div className="ai-panel">
          <SourcePanel
            collapsed={leftCollapsed}
            onToggleCollapsed={() => {
              setLeftCollapsed((v) => !v);
              if (!leftCollapsed) setKbPreviewOpen(false);
            }}
            courseId={resolvedCourseId}
            onPreviewStateChange={(open) => setKbPreviewOpen(open)}
          />
        </div>
      </div>

      <div className="ai-studio-content">
        <div className="ai-panel">
          <ChatPanel />
        </div>
      </div>

      <div className="ai-studio-sider">
        <div className="ai-panel">
          <StudioPanel
            collapsed={rightCollapsed}
            onToggleCollapsed={() => setRightCollapsed((v) => !v)}
          />
        </div>
      </div>
    </div>
  );
}
