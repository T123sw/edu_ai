import React, { useState } from 'react';
import { Layout } from 'antd';
import SourcePanel from '../../components/student/SourcePanel';
import ChatPanel from '../../components/student/ChatPanel';
import StudioPanel from '../../components/student/StudioPanel';
import './TeacherStudioPage.css';

const LEFT_EXPANDED_WIDTH = '22%';
const LEFT_COLLAPSED_WIDTH = 72;
const RIGHT_EXPANDED_WIDTH = '30%';
const RIGHT_COLLAPSED_WIDTH = 72;

interface TeacherStudioPageProps {
  courseId?: string;
  courseName?: string;
}

export default function TeacherStudioPage({ courseId, courseName }: TeacherStudioPageProps) {
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  return (
    <Layout 
      className="teacher-studio-layout"
      style={{ 
        height: 'calc(100vh - 64px)', 
        background: '#f0f2f5', 
        padding: 8, 
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'row'
      }}
    >
        <Layout.Sider
          width={leftCollapsed ? LEFT_COLLAPSED_WIDTH : LEFT_EXPANDED_WIDTH}
          style={{ 
            background: 'transparent', 
            paddingRight: 8, 
            minHeight: 0,
            height: '100%',
            overflow: 'hidden'
          }}
        >
          <SourcePanel
            collapsed={leftCollapsed}
            onToggleCollapsed={() => setLeftCollapsed((v) => !v)}
            courseId={courseId}
          />
        </Layout.Sider>

        <Layout.Content 
          style={{ 
            background: 'transparent', 
            minHeight: 0,
            height: '100%',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
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
            overflow: 'hidden'
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
