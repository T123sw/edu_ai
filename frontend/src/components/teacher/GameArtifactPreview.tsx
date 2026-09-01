import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Divider, Space, Spin, Typography } from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, RightOutlined } from '@ant-design/icons';

import type { GeneratedFile } from '../../store/teacher/useStore';
import { getTeacherAuthToken, resolveGameHtmlUrl } from '../../services/teacher/gameAssets';

const { Title } = Typography;

type Props = {
  file: GeneratedFile;
  onBack: () => void;
  onToggleCollapsed: () => void;
};

export default function GameArtifactPreview({ file, onBack, onToggleCollapsed }: Props) {
  const htmlUrl = useMemo(() => resolveGameHtmlUrl(file.meta?.htmlUrl), [file.meta?.htmlUrl]);
  const [htmlContent, setHtmlContent] = useState('');
  const [blobUrl, setBlobUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState('');

  useEffect(() => {
    let cancelled = false;
    let nextBlobUrl = '';

    if (!htmlUrl) {
      setHtmlContent('');
      setBlobUrl('');
      setErrorText('页面资源不存在，请重新生成小游戏。');
      return;
    }

    setLoading(true);
    setErrorText('');
    setHtmlContent('');
    setBlobUrl('');

    const token = getTeacherAuthToken();
    fetch(htmlUrl, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`小游戏页面加载失败: ${response.status}`);
        }
        return response.text();
      })
      .then((html) => {
        if (cancelled) {
          return;
        }
        nextBlobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
        setHtmlContent(html);
        setBlobUrl(nextBlobUrl);
      })
      .catch((error: any) => {
        if (!cancelled) {
          setErrorText(error?.message || '小游戏页面加载失败，请重新生成。');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (nextBlobUrl) {
        URL.revokeObjectURL(nextBlobUrl);
      }
    };
  }, [htmlUrl]);

  return (
    <div
      className="edu-rich-preview"
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
            disabled={!blobUrl && !htmlUrl}
            onClick={() => (blobUrl || htmlUrl) && window.open(blobUrl || htmlUrl, '_blank', 'noopener,noreferrer')}
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

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, minHeight: 240 }}>
          <Spin tip="正在加载小游戏..." />
        </div>
      ) : errorText ? (
        <Alert type="warning" showIcon message={errorText} />
      ) : htmlContent ? (
        <iframe
          title={file.name}
          srcDoc={htmlContent}
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
