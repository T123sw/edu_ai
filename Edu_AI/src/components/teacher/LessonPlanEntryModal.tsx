import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Form, Input, Modal, Skeleton, Space, Typography, message } from 'antd';
import { fetchLessonPlanEntryCardsV2, type LessonPlanEntryCard } from '../../services/teacher/chatV2';
import {
  getDefaultLessonPlanPresetCards,
  groupLessonPlanEntryCards,
  type LessonPlanEntryConfigInput,
} from '../../services/teacher/lessonPlanEntry.helpers';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';
import './LessonPlanEntryModal.css';

const { Text, Title } = Typography;

type EntryState = 'idle' | 'cards_loading' | 'cards_ready' | 'editing_config' | 'generating' | 'completed' | 'error';

type Props = {
  open: boolean;
  selectedDocIds: string[];
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { card: LessonPlanEntryCard; config: LessonPlanEntryConfigInput }) => Promise<void> | void;
};

export default function LessonPlanEntryModal({
  open,
  selectedDocIds,
  courseId,
  workspaceScope,
  submitting = false,
  onCancel,
  onSubmit,
}: Props) {
  const [entryState, setEntryState] = useState<EntryState>('idle');
  const [cards, setCards] = useState<LessonPlanEntryCard[]>(getDefaultLessonPlanPresetCards());
  const [selectedCard, setSelectedCard] = useState<LessonPlanEntryCard | null>(null);
  const [loadError, setLoadError] = useState('');
  const [configForm] = Form.useForm<LessonPlanEntryConfigInput>();

  useEffect(() => {
    if (!open) {
      setEntryState('idle');
      setCards(getDefaultLessonPlanPresetCards());
      setSelectedCard(null);
      setLoadError('');
      configForm.resetFields();
      return;
    }

    if (!selectedDocIds.length) {
      setEntryState('error');
      setCards(getDefaultLessonPlanPresetCards());
      setLoadError('请先勾选至少一份文档。');
      return;
    }

    let cancelled = false;
    setEntryState('cards_loading');
    setLoadError('');
    fetchLessonPlanEntryCardsV2({
      course_id: courseId,
      scope_type: workspaceScope?.scopeType,
      scope_id: workspaceScope?.scopeId,
      selected_doc_ids: selectedDocIds,
    })
      .then((response) => {
        if (cancelled) return;
        const nextCards = Array.isArray(response.cards) && response.cards.length > 0
          ? response.cards
          : getDefaultLessonPlanPresetCards();
        setCards(nextCards);
        setEntryState('cards_ready');
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setCards(getDefaultLessonPlanPresetCards());
        setEntryState('error');
        setLoadError(error.message || '加载教案推荐失败');
      });

    return () => {
      cancelled = true;
    };
  }, [open, selectedDocIds, courseId, configForm, workspaceScope]);

  const visibleCards = useMemo(
    () => cards.filter((card) => card.card_id !== 'preset-inquiry-lesson' && card.preset_key !== 'inquiry_lesson'),
    [cards],
  );
  const groupedCards = useMemo(() => groupLessonPlanEntryCards(visibleCards), [visibleCards]);

  const switchToCard = (card: LessonPlanEntryCard) => {
    setSelectedCard(card);
    configForm.setFieldsValue({
      topic: card.prefill_config?.topic || '',
      audience: card.prefill_config?.audience || '',
      duration: card.prefill_config?.duration || '45分钟',
      lessonType: card.prefill_config?.lesson_type || '',
      objective: card.prefill_config?.objective || '',
      keyPoints: Array.isArray(card.prefill_config?.key_points) ? card.prefill_config?.key_points.join('；') : '',
      difficultPoints: Array.isArray(card.prefill_config?.difficult_points)
        ? card.prefill_config?.difficult_points.join('；')
        : '',
      afterClassTask: card.prefill_config?.after_class_task || '',
      styleHint: card.prefill_config?.style_hint || '',
      extraRequirements: '先生成大纲，确认后再生成正文。',
    });
    setEntryState('editing_config');
  };

  const handleSubmit = async () => {
    if (!selectedCard) {
      message.warning('请先选择一种教案方向。');
      return;
    }
    const values = await configForm.validateFields();
    setEntryState('generating');
    try {
      await onSubmit({
        card: selectedCard,
        config: values,
      });
      setEntryState('completed');
    } catch {
      setEntryState('editing_config');
    }
  };

  const renderCards = (items: LessonPlanEntryCard[]) => (
    <div className="lesson-plan-entry-modal__card-grid">
      {items.map((card) => (
        <button
          key={card.card_id}
          type="button"
          className="lesson-plan-entry-modal__card"
          onClick={() => switchToCard(card)}
        >
          <span className="lesson-plan-entry-modal__card-title">{card.title}</span>
          <span className="lesson-plan-entry-modal__card-description">{card.description}</span>
        </button>
      ))}
    </div>
  );

  return (
    <Modal
      title={selectedCard ? '配置教案要求' : '创建教案'}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={1040}
      destroyOnClose
      className="lesson-plan-entry-modal"
    >
      {entryState === 'cards_loading' ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
          <Skeleton active paragraph={{ rows: 3 }} />
        </Space>
      ) : null}

      {(entryState === 'cards_ready' || entryState === 'error') && (
        <Space className="lesson-plan-entry-modal__body" direction="vertical" size={0} style={{ width: '100%' }}>
          {loadError ? <Alert type="warning" showIcon message={loadError} /> : null}

          <div className="lesson-plan-entry-modal__section">
            <Title level={5} className="lesson-plan-entry-modal__section-title">固定模板</Title>
            {renderCards(groupedCards.presets)}
          </div>

          <div className="lesson-plan-entry-modal__section">
            <Title level={5} className="lesson-plan-entry-modal__section-title">系统推荐</Title>
            {renderCards(groupedCards.recommended)}
          </div>
        </Space>
      )}

      {(entryState === 'editing_config' || entryState === 'generating' || entryState === 'completed') && selectedCard ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div>
            <Space direction="vertical" size={4}>
              <Title level={5} style={{ marginBottom: 0 }}>
                {selectedCard.title}
              </Title>
              <Text type="secondary">{selectedCard.description}</Text>
              <Text type="secondary">系统会先生成大纲，确认后再生成正文。</Text>
            </Space>
          </div>

          <Form form={configForm} layout="vertical">
            <Form.Item
              label="课题"
              name="topic"
              rules={[{ required: true, message: '请输入课题' }]}
            >
              <Input placeholder="例如：关羽的战绩与历史评价" />
            </Form.Item>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
              <Form.Item label="适用对象" name="audience">
                <Input placeholder="例如：初中历史" />
              </Form.Item>
              <Form.Item label="课时长度" name="duration">
                <Input placeholder="例如：45分钟" />
              </Form.Item>
              <Form.Item label="课型" name="lessonType">
                <Input placeholder="例如：新授课/复习课/探究课" />
              </Form.Item>
            </div>

            <Form.Item label="本课目标" name="objective">
              <Input placeholder="例如：梳理战绩并进行历史评价" />
            </Form.Item>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Form.Item label="教学重点" name="keyPoints">
                <Input.TextArea
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  placeholder="例如：核心概念；材料证据；方法迁移"
                />
              </Form.Item>
              <Form.Item label="教学难点" name="difficultPoints">
                <Input.TextArea
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  placeholder="例如：概念辨析；证据与结论的对应关系"
                />
              </Form.Item>
            </div>

            <Form.Item label="课后任务" name="afterClassTask">
              <Input placeholder="例如：完成一段材料分析或一组分层练习" />
            </Form.Item>

            <Form.Item label="风格约束" name="styleHint">
              <Input placeholder="例如：贴近真实课堂，突出问题链和史料分析" />
            </Form.Item>

            <Form.Item label="补充要求" name="extraRequirements">
              <Input.TextArea
                autoSize={{ minRows: 4, maxRows: 8 }}
                placeholder="例如：先生成大纲，确认后再生成正文；作业要区分必做和选做"
              />
            </Form.Item>
          </Form>

          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Button onClick={() => setEntryState('cards_ready')} disabled={submitting}>
              返回卡片
            </Button>
            <Button type="primary" onClick={handleSubmit} loading={submitting}>
              生成大纲
            </Button>
          </Space>
        </Space>
      ) : null}
    </Modal>
  );
}
