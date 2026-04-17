import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Empty, Modal, Skeleton, Space, Typography } from 'antd';
import { getTeachingVideoPpts, type TeachingVideoPptItem } from '../../services/teacher/api';

const { Paragraph, Text, Title } = Typography;

type Props = {
  open: boolean;
  courseId?: string;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { pptMaterialId: string; pptTitle: string }) => Promise<void> | void;
};

export default function TeachingVideoEntryModal({
  open,
  courseId,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [items, setItems] = useState<TeachingVideoPptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState('');
  const [selectedId, setSelectedId] = useState('');

  useEffect(() => {
    if (!open) {
      setItems([]);
      setLoading(false);
      setErrorText('');
      setSelectedId('');
      return;
    }

    if (!courseId) {
      setItems([]);
      setLoading(false);
      setErrorText('请先进入具体课程后，再选择教学视频素材。');
      return;
    }

    let cancelled = false;
    setLoading(true);
    setErrorText('');

    getTeachingVideoPpts(courseId)
      .then((response) => {
        if (cancelled) return;
        setItems(response);
        setSelectedId(response[0]?.material_id || '');
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setItems([]);
        setSelectedId('');
        setErrorText(error.message || '加载可用 PPT 列表失败');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [courseId, open]);

  const selectedItem = useMemo(
    () => items.find((item) => item.material_id === selectedId) || null,
    [items, selectedId],
  );

  const handleSubmit = async () => {
    if (!selectedItem) {
      return;
    }
    await onSubmit({
      pptMaterialId: selectedItem.material_id,
      pptTitle: selectedItem.title,
    });
  };

  return (
    <Modal
      title="创建教学视频"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={860}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Text type="secondary">
          这里展示的是后端已经生成完成、并且保留了 `content.md` 的 PPT。选中后系统会自动把对应的 PPT 和内容稿送入教学视频模块。
        </Text>

        {errorText ? <Alert type="warning" showIcon message={errorText} /> : null}

        {loading ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Skeleton active paragraph={{ rows: 3 }} />
            <Skeleton active paragraph={{ rows: 3 }} />
          </Space>
        ) : null}

        {!loading && !errorText && items.length === 0 ? (
          <Empty
            description="当前课程还没有可用于教学视频的 PPT。请先在生成工场中完成 PPT 生成。"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 12,
            }}
          >
            {items.map((item) => {
              const active = item.material_id === selectedId;
              return (
                <Card
                  key={item.material_id}
                  hoverable
                  size="small"
                  onClick={() => setSelectedId(item.material_id)}
                  style={{
                    borderRadius: 14,
                    borderColor: active ? '#1677ff' : undefined,
                    boxShadow: active ? '0 0 0 1px rgba(22,119,255,0.18)' : undefined,
                  }}
                >
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Title level={5} style={{ margin: 0 }}>
                      {item.title}
                    </Title>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {typeof item.slide_count === 'number' && item.slide_count > 0
                        ? `共 ${item.slide_count} 页`
                        : '页数信息未返回'}
                    </Paragraph>
                    {item.updated_at ? (
                      <Text type="secondary">最近更新：{new Date(item.updated_at).toLocaleString()}</Text>
                    ) : null}
                  </Space>
                </Card>
              );
            })}
          </div>
        ) : null}

        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Text type="secondary">
            {selectedItem ? `当前已选：${selectedItem.title}` : '请选择一个 PPT'}
          </Text>
          <Space>
            <Button onClick={onCancel} disabled={submitting}>
              取消
            </Button>
            <Button type="primary" onClick={handleSubmit} loading={submitting} disabled={!selectedItem}>
              生成教学视频
            </Button>
          </Space>
        </Space>
      </Space>
    </Modal>
  );
}
