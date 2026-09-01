import { useMemo, useState } from 'react';
import { ArrowLeftOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Card, Progress, Space, Tag, Typography } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';

const { Text, Title } = Typography;

type Flashcard = {
  id?: string;
  front: string;
  back: string;
  category?: string;
  source_doc_id?: string | null;
};

type Props = {
  file: GeneratedFile;
  onBack: () => void;
  onToggleCollapsed: () => void;
};

export function normalizeFlashcardContent(content: unknown): Flashcard[] {
  const payload = content && typeof content === 'object' ? content as Record<string, unknown> : {};
  const cards = Array.isArray(payload.cards) ? payload.cards : [];
  return cards
    .map((item, index) => {
      const card = item && typeof item === 'object' ? item as Record<string, unknown> : {};
      return {
        id: String(card.id || `card-${index + 1}`),
        front: String(card.front || '').trim(),
        back: String(card.back || '').trim(),
        category: String(card.category || '').trim() || undefined,
        source_doc_id: String(card.source_doc_id || '').trim() || undefined,
      };
    })
    .filter((card) => card.front && card.back);
}

export default function FlashcardArtifactPreview({
  file,
  onBack,
  onToggleCollapsed,
}: Props) {
  const cards = useMemo(() => normalizeFlashcardContent(file.content), [file.content]);
  const [index, setIndex] = useState(0);
  const [showBack, setShowBack] = useState(false);
  const card = cards[index];

  const move = (next: number) => {
    setIndex(Math.max(0, Math.min(cards.length - 1, next)));
    setShowBack(false);
  };

  return (
    <div className="flashcard-preview edu-rich-preview">
      <div className="flashcard-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>返回</Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>
      <div className="flashcard-preview__heading">
        <div>
          <Title level={4}>{file.name}</Title>
          <Text type="secondary">点击卡片翻面，逐张检查正反面与资料来源。</Text>
        </div>
        <Text strong>{cards.length ? `${index + 1} / ${cards.length}` : '0 / 0'}</Text>
      </div>
      <Progress
        percent={cards.length ? Math.round(((index + 1) / cards.length) * 100) : 0}
        showInfo={false}
      />
      {card ? (
        <Card
          className={`flashcard-preview__card${showBack ? ' is-back' : ''}`}
          onClick={() => setShowBack((value) => !value)}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setShowBack((value) => !value);
            }
          }}
        >
          <Text type="secondary">{showBack ? '答案' : '问题'}</Text>
          <div className="flashcard-preview__content">
            {showBack ? card.back : card.front}
          </div>
          <Space wrap>
            {card.category ? <Tag>{card.category}</Tag> : null}
            {card.source_doc_id ? <Tag color="blue">来源：{card.source_doc_id}</Tag> : null}
          </Space>
        </Card>
      ) : (
        <div className="flashcard-preview__empty">该资源没有可用的闪卡内容。</div>
      )}
      <div className="flashcard-preview__actions">
        <Button
          icon={<LeftOutlined />}
          disabled={index <= 0}
          onClick={() => move(index - 1)}
        >
          上一张
        </Button>
        <Button onClick={() => setShowBack((value) => !value)}>
          {showBack ? '查看问题' : '查看答案'}
        </Button>
        <Button
          disabled={index >= cards.length - 1}
          onClick={() => move(index + 1)}
        >
          下一张
          <RightOutlined />
        </Button>
      </div>
    </div>
  );
}

