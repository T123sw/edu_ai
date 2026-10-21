import { FlashcardRound } from "../flashcards/FlashcardRound";
import { useMemo } from 'react';
import { ArrowLeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Typography } from 'antd';
import type { GeneratedFile } from '../../store/teacher/useStore';

const { Text, Title } = Typography;

type Flashcard = {
  id?: string;
  front: string;
  back: string;
  category?: string;
  source_doc_id?: string | null;
  source_title?: string;
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
        source_title: String(card.source_title || '').trim() || undefined,
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
  return (
    <div className="flashcard-preview edu-rich-preview">
      <div className="flashcard-preview__toolbar">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack}>返回</Button>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>
      <div className="flashcard-preview__heading">
        <div>
          <Title level={4}>{file.name}</Title>
          <Text type="secondary">点击卡片翻面，按记忆情况选择再练一次或已经掌握。</Text>
        </div>
        <Text strong>{cards.length} 张卡片</Text>
      </div>
      <FlashcardRound key={JSON.stringify(cards)} cards={cards} />
    </div>
  );
}
