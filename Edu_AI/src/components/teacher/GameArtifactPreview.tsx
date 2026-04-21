import React from 'react';
import { Alert, Button, Divider, Space, Typography } from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, RightOutlined } from '@ant-design/icons';

import type { GeneratedFile } from '../../store/teacher/useStore';

const { Title } = Typography;

type Props = {
  file: GeneratedFile;
  onBack: () => void;
  onToggleCollapsed: () => void;
};

export default function GameArtifactPreview({ file, onBack, onToggleCollapsed }: Props) {
  const htmlUrl = String(file.meta?.htmlUrl || '').trim();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#ffffff',
        borderRadius: 12,
        padding: 24,
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} style={{ marginLeft: -12 }}>
          返回
        </Button>
        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            disabled={!htmlUrl}
            onClick={() => htmlUrl && window.open(htmlUrl, '_blank', 'noopener,noreferrer')}
          >
            全屏播放
          </Button>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作台" />
        </Space>
      </div>

      <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
        {file.name}
      </Title>
      <Divider style={{ flexShrink: 0 }} />

      {htmlUrl ? (
        <iframe
          title={file.name}
          src={htmlUrl}
          style={{
            width: '100%',
            flex: 1,
            minHeight: 0,
            border: '1px solid #f0f0f0',
            borderRadius: 16,
            background: '#fff',
          }}
        />
      ) : (
        <Alert type="warning" showIcon message="页面资源不存在，请重新生成小游戏。" />
      )}
    </div>
  );
}
