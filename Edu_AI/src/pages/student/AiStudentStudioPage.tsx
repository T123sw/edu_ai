import React, { useState } from 'react';
import { Layout } from 'antd';
import SourcePanel from '../../components/student/SourcePanel';
import ChatPanel from '../../components/student/ChatPanel';
import StudioPanel from '../../components/student/StudioPanel';

const LEFT_EXPANDED_WIDTH = '22%';
const LEFT_PREVIEW_WIDTH = '38%';
const LEFT_COLLAPSED_WIDTH = 72;
const RIGHT_EXPANDED_WIDTH = '30%';
const RIGHT_COLLAPSED_WIDTH = 72;

interface AiStudentStudioPageProps {
  courseId?: string;
}

export default function AiStudentStudioPage({ courseId }: AiStudentStudioPageProps) {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(true); // 学生端右侧面板默认收起
  const [kbPreviewOpen, setKbPreviewOpen] = useState(false);

  const leftWidth = leftCollapsed
    ? LEFT_COLLAPSED_WIDTH
    : (kbPreviewOpen ? LEFT_PREVIEW_WIDTH : LEFT_EXPANDED_WIDTH);

  return (
    <Layout
      style={{
        height: '100%',
        background: '#f0f2f5',
        padding: 8,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'row',
      }}
    >
      <Layout.Sider
        width={leftWidth}
        style={{
          background: 'transparent',
          paddingRight: 8,
          minHeight: 0,
          height: '100%',
          overflow: 'hidden',
          transition: 'width 0.2s',
        }}
      >
        <SourcePanel
          collapsed={leftCollapsed}
          onToggleCollapsed={() => {
            setLeftCollapsed((v) => !v);
            if (!leftCollapsed) setKbPreviewOpen(false);
          }}
          courseId={courseId}
          onPreviewStateChange={(open) => setKbPreviewOpen(open)}
        />
      </Layout.Sider>

      <Layout.Content
        style={{
          background: 'transparent',
          minHeight: 0,
          height: '100%',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <ChatPanel />
      </Layout.Content>

      <Layout.Sider
        width={rightCollapsed ? RIGHT_COLLAPSED_WIDTH : RIGHT_EXPANDED_WIDTH}
        style={{
          background: 'transparent',
          paddingLeft: 8,
          minHeight: 0,
          height: '100%',
          overflow: 'hidden',
          transition: 'width 0.2s',
        }}
      >
        <StudioPanel
          collapsed={rightCollapsed}
          onToggleCollapsed={() => setRightCollapsed((v) => !v)}
        />
      </Layout.Sider>
    </Layout>
  );
}

