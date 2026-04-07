import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Input, Modal, Skeleton, Space, Typography, message } from 'antd';
import { fetchReportEntryCardsV2, type ReportEntryCard } from '../../services/teacher/chatV2';
import { createDraftCacheKey, getDefaultPresetCards, groupReportEntryCards, shouldConfirmCardSwitch } from '../../services/teacher/reportEntry.helpers';

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;

type EntryState = 'idle' | 'cards_loading' | 'cards_ready' | 'editing_prompt' | 'generating' | 'completed' | 'error';

type Props = {
  open: boolean;
  selectedDocIds: string[];
  courseId?: string;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { question: string; promptDraft: string; card: ReportEntryCard }) => Promise<void> | void;
};

export default function ReportEntryModal({
  open,
  selectedDocIds,
  courseId,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [entryState, setEntryState] = useState<EntryState>('idle');
  const [cards, setCards] = useState<ReportEntryCard[]>(getDefaultPresetCards());
  const [selectedCard, setSelectedCard] = useState<ReportEntryCard | null>(null);
  const [draftMap, setDraftMap] = useState<Record<string, string>>({});
  const [editorText, setEditorText] = useState('');
  const [draftDirty, setDraftDirty] = useState(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!open) {
      setEntryState('idle');
      setSelectedCard(null);
      setDraftMap({});
      setEditorText('');
      setDraftDirty(false);
      setLoadError('');
      setCards(getDefaultPresetCards());
      return;
    }

    if (!selectedDocIds.length) {
      setEntryState('error');
      setLoadError('请先选择至少一份知识库文档。');
      setCards(getDefaultPresetCards());
      return;
    }

    let cancelled = false;
    setEntryState('cards_loading');
    setLoadError('');
    fetchReportEntryCardsV2({
      course_id: courseId,
      selected_doc_ids: selectedDocIds,
    })
      .then((response) => {
        if (cancelled) return;
        const nextCards = Array.isArray(response.cards) && response.cards.length > 0 ? response.cards : getDefaultPresetCards();
        setCards(nextCards);
        setEntryState('cards_ready');
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setCards(getDefaultPresetCards());
        setEntryState('error');
        setLoadError(error.message || '加载报告卡片失败');
      });

    return () => {
      cancelled = true;
    };
  }, [open, selectedDocIds, courseId]);

  const groupedCards = useMemo(() => groupReportEntryCards(cards), [cards]);

  const switchToCard = (card: ReportEntryCard) => {
    if (
      shouldConfirmCardSwitch({
        currentCardId: selectedCard?.card_id,
        nextCardId: card.card_id,
        draftDirty,
      }) &&
      typeof window !== 'undefined' &&
      !window.confirm('当前已编辑内容尚未生成，切换卡片将保留当前草稿到本次弹窗会话中，继续吗？')
    ) {
      return;
    }

    const cacheKey = createDraftCacheKey(card);
    const nextEditorText = draftMap[cacheKey] || card.prompt_draft;
    setSelectedCard(card);
    setEditorText(nextEditorText);
    setDraftDirty(nextEditorText !== card.prompt_draft);
    setEntryState('editing_prompt');
  };

  const handleEditorChange = (value: string) => {
    setEditorText(value);
    if (selectedCard) {
      const cacheKey = createDraftCacheKey(selectedCard);
      setDraftMap((prev) => ({ ...prev, [cacheKey]: value }));
      setDraftDirty(value !== selectedCard.prompt_draft);
    }
  };

  const handleSubmit = async () => {
    if (!selectedCard) {
      message.warning('请先选择一个报告方向。');
      return;
    }
    const question = editorText.trim();
    if (!question) {
      message.warning('请补充报告要求后再生成。');
      return;
    }

    setEntryState('generating');
    try {
      await onSubmit({
        question,
        promptDraft: selectedCard.prompt_draft,
        card: selectedCard,
      });
      setEntryState('completed');
    } catch {
      setEntryState('editing_prompt');
    }
  };

  const renderCards = (items: ReportEntryCard[]) => (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}
    >
      {items.map((card) => (
        <Card
          key={card.card_id}
          hoverable
          size="small"
          onClick={() => switchToCard(card)}
          style={{ borderRadius: 12 }}
        >
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            <Text strong>{card.title}</Text>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              {card.description}
            </Paragraph>
          </Space>
        </Card>
      ))}
    </div>
  );

  return (
    <Modal
      title={selectedCard ? '编辑报告要求' : '创建报告'}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={860}
      destroyOnClose
    >
      {entryState === 'cards_loading' ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
          <Skeleton active paragraph={{ rows: 3 }} />
        </Space>
      ) : null}

      {(entryState === 'cards_ready' || entryState === 'error') && (
        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          {loadError ? <Alert type="warning" showIcon message={loadError} /> : null}

          <div>
            <Title level={5}>固定模板</Title>
            {renderCards(groupedCards.presets)}
          </div>

          <div>
            <Title level={5}>系统推荐</Title>
            {renderCards(groupedCards.recommended)}
          </div>
        </Space>
      )}

      {(entryState === 'editing_prompt' || entryState === 'generating' || entryState === 'completed') && selectedCard ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div>
            <Space direction="vertical" size={4}>
              <Title level={5} style={{ marginBottom: 0 }}>
                {selectedCard.title}
              </Title>
              <Text type="secondary">{selectedCard.description}</Text>
            </Space>
          </div>

          <TextArea
            value={editorText}
            onChange={(event) => handleEditorChange(event.target.value)}
            autoSize={{ minRows: 8, maxRows: 16 }}
            placeholder="请输入你希望生成的报告要求"
            disabled={submitting}
          />

          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Button onClick={() => setEntryState('cards_ready')} disabled={submitting}>
              返回卡片
            </Button>
            <Button type="primary" onClick={handleSubmit} loading={submitting}>
              生成报告
            </Button>
          </Space>
        </Space>
      ) : null}
    </Modal>
  );
}
