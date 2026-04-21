import React, { useMemo, useState } from 'react';
import { Alert, Button, Card, Modal, Space, Typography } from 'antd';

import type { GameTypeV2 } from '../../services/teacher/chatV2';

const { Paragraph, Text, Title } = Typography;

const GAME_OPTIONS: Array<{
  value: GameTypeV2;
  title: string;
  description: string;
  sampleUseCase: string;
}> = [
  {
    value: 'category_sort',
    title: '分类归纳',
    description: '把知识点拖入正确类别，适合梳理概念分组和章节结构。',
    sampleUseCase: '适合概念分类、史实归纳、语法分组。',
  },
  {
    value: 'drag_match',
    title: '拖拽配对',
    description: '把术语与定义、人物与事件、现象与原因快速配对。',
    sampleUseCase: '适合名词释义、人物事件、公式含义。',
  },
  {
    value: 'memory_flip',
    title: '翻牌记忆',
    description: '通过翻牌找到对应关系，强化课堂记忆和复习。',
    sampleUseCase: '适合术语记忆、英汉对应、定义复习。',
  },
];

type Props = {
  open: boolean;
  selectedDocIds: string[];
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { gameType: GameTypeV2 }) => void;
};

export default function GameEntryModal({
  open,
  selectedDocIds,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [selectedGameType, setSelectedGameType] = useState<GameTypeV2 | null>(null);
  const canSubmit = selectedDocIds.length > 0 && Boolean(selectedGameType);
  const selectedOption = useMemo(
    () => GAME_OPTIONS.find((item) => item.value === selectedGameType) || null,
    [selectedGameType],
  );

  return (
    <Modal
      title="生成小游戏"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={760}
      destroyOnClose
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type={selectedDocIds.length > 0 ? 'info' : 'warning'}
          showIcon
          message={
            selectedDocIds.length > 0
              ? `已选 ${selectedDocIds.length} 份资料，请选择一种小游戏。`
              : '请先勾选至少一份知识库文档。'
          }
        />

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 12,
          }}
        >
          {GAME_OPTIONS.map((option) => {
            const isSelected = selectedGameType === option.value;
            return (
              <Card
                key={option.value}
                hoverable
                onClick={() => setSelectedGameType(option.value)}
                style={{
                  borderColor: isSelected ? '#1677ff' : '#f0f0f0',
                  boxShadow: isSelected ? '0 0 0 2px rgba(22,119,255,0.12)' : 'none',
                }}
              >
                <Space direction="vertical" size={8}>
                  <Title level={5} style={{ margin: 0 }}>
                    {option.title}
                  </Title>
                  <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    {option.description}
                  </Paragraph>
                  <Text type="secondary">{option.sampleUseCase}</Text>
                </Space>
              </Card>
            );
          })}
        </div>

        {selectedOption && (
          <Alert
            type="success"
            showIcon
            message={`当前选择：${selectedOption.title}`}
            description={selectedOption.sampleUseCase}
          />
        )}

        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button onClick={onCancel} disabled={submitting}>
            取消
          </Button>
          <Button
            type="primary"
            loading={submitting}
            disabled={!canSubmit}
            onClick={() => selectedGameType && onSubmit({ gameType: selectedGameType })}
          >
            生成小游戏
          </Button>
        </Space>
      </Space>
    </Modal>
  );
}
