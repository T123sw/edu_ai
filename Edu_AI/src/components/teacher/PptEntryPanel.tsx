import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Radio, Select, Skeleton, Space, Typography, message } from 'antd';
import {
  fetchPptEntryCardsV2,
  type ChatDirectPptGenerateResponseV2,
  type ChatDirectPptOutlineResponseV2,
  type PptEntryCard,
} from '../../services/teacher/chatV2';
import type { DirectPptEntryConfigInput } from '../../services/teacher/pptEntry.helpers';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;

type EntryState = 'idle' | 'cards_loading' | 'cards_ready' | 'outline_loading' | 'outline_ready' | 'generating' | 'error';

type LengthOption = 'short' | 'medium' | 'long';

const DEFAULT_PPT_CARDS: PptEntryCard[] = [
  {
    card_id: 'preset-knowledge-lecture',
    card_type: 'preset',
    title: '知识讲解型',
    description: '适合概念定义、原理机制和课堂讲解。',
    preset_key: 'knowledge_lecture',
    objective_hint: '课堂讲解',
    length_option: 'medium',
    style_hint: '逻辑清晰、层次分明',
  },
  {
    card_id: 'preset-topic-briefing',
    card_type: 'preset',
    title: '主题分享型',
    description: '适合专题汇报、课程展示和公开分享。',
    preset_key: 'topic_briefing',
    objective_hint: '主题分享',
    length_option: 'medium',
    style_hint: '重点突出、表达流畅',
  },
  {
    card_id: 'preset-comparison-analysis',
    card_type: 'preset',
    title: '对比分析型',
    description: '适合多文档、多方案、多观点之间的比较展示。',
    preset_key: 'comparison_analysis',
    objective_hint: '对比分析',
    length_option: 'long',
    style_hint: '先归类后对比，最后形成结论',
  },
  {
    card_id: 'preset-defense-summary',
    card_type: 'preset',
    title: '汇报答辩型',
    description: '适合课程汇报、项目展示和答辩总结。',
    preset_key: 'defense_summary',
    objective_hint: '汇报答辩',
    length_option: 'short',
    style_hint: '结论先行，表达凝练',
  },
];

export interface DirectPptEntryFormValue {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: LengthOption;
  keyPointsText?: string;
  generalRequirements?: string;
  styleHint?: string;
  specialRequirements?: string;
}

type Props = {
  open: boolean;
  selectedDocIds: string[];
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  submitting?: boolean;
  onCancel: () => void;
  onSubmitOutline: (payload: { config: DirectPptEntryConfigInput }) => Promise<ChatDirectPptOutlineResponseV2>;
  onSubmitGenerate: (payload: { draftId: string; outline?: Record<string, unknown> }) => Promise<ChatDirectPptGenerateResponseV2>;
};

function normalizeKeyPoints(value: string): string[] {
  return String(value || '')
    .split(/\r?\n|,|，|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function findOutlineContent(response: ChatDirectPptOutlineResponseV2): Record<string, unknown> | undefined {
  const artifacts = Array.isArray(response.artifacts) ? response.artifacts : [];
  const outlineArtifact = artifacts.find((item) => String((item as any)?.artifact_type || '').trim() === 'ppt_outline') as
    | Record<string, unknown>
    | undefined;
  const content = outlineArtifact?.content;
  if (content && typeof content === 'object') {
    return content as Record<string, unknown>;
  }
  return undefined;
}

function groupPptCards(cards: PptEntryCard[]): { presets: PptEntryCard[]; recommended: PptEntryCard[] } {
  return {
    presets: cards.filter((card) => card.card_type === 'preset'),
    recommended: cards.filter((card) => card.card_type === 'recommended'),
  };
}

function getInitialFormValues(): DirectPptEntryFormValue {
  return {
    deckTitle: '',
    deckSubtitle: '',
    audience: '',
    objective: '',
    themeId: 'heu_academic_elegant',
    lengthOption: 'medium',
    keyPointsText: '',
    generalRequirements: '',
    styleHint: '',
    specialRequirements: '',
  };
}

export default function PptEntryPanel({
  open,
  selectedDocIds,
  courseId,
  workspaceScope,
  submitting = false,
  onCancel,
  onSubmitOutline,
  onSubmitGenerate,
}: Props) {
  const [form] = Form.useForm<DirectPptEntryFormValue>();
  const [entryState, setEntryState] = useState<EntryState>('idle');
  const [cards, setCards] = useState<PptEntryCard[]>(DEFAULT_PPT_CARDS);
  const [selectedCard, setSelectedCard] = useState<PptEntryCard | null>(null);
  const [draftId, setDraftId] = useState('');
  const [outlineText, setOutlineText] = useState('');
  const [errorText, setErrorText] = useState('');

  useEffect(() => {
    if (!open) {
      setEntryState('idle');
      setCards(DEFAULT_PPT_CARDS);
      setSelectedCard(null);
      setDraftId('');
      setOutlineText('');
      setErrorText('');
      form.resetFields();
      return;
    }

    form.setFieldsValue(getInitialFormValues());

    if (!selectedDocIds.length) {
      setEntryState('error');
      setCards(DEFAULT_PPT_CARDS);
      setErrorText('请先选择至少一份知识库文档。');
      return;
    }

    let cancelled = false;
    setEntryState('cards_loading');
    setErrorText('');

    fetchPptEntryCardsV2({
      course_id: courseId,
      scope_type: workspaceScope?.scopeType,
      scope_id: workspaceScope?.scopeId,
      selected_doc_ids: selectedDocIds,
    })
      .then((response) => {
        if (cancelled) return;
        const nextCards = Array.isArray(response.cards) && response.cards.length > 0 ? response.cards : DEFAULT_PPT_CARDS;
        setCards(nextCards);
        setEntryState('cards_ready');
      })
      .catch((error: Error) => {
        if (cancelled) return;
        setCards(DEFAULT_PPT_CARDS);
        setEntryState('cards_ready');
        setErrorText(error.message || 'PPT 推荐卡片加载失败');
      });

    return () => {
      cancelled = true;
    };
  }, [courseId, form, open, selectedDocIds, workspaceScope]);

  const groupedCards = useMemo(() => groupPptCards(cards), [cards]);

  const applyCardDefaults = (card: PptEntryCard) => {
    setSelectedCard(card);
    form.setFieldsValue({
      objective: card.objective_hint || '',
      lengthOption: card.length_option || 'medium',
      styleHint: card.style_hint || '',
    });
  };

  const handleBuildOutline = async () => {
    if (!selectedDocIds.length) {
      message.warning('请先选择至少一份知识库文档。');
      return;
    }

    try {
      const values = await form.validateFields();
      setEntryState('outline_loading');
      setErrorText('');
      const response = await onSubmitOutline({
        config: {
          deckTitle: values.deckTitle,
          deckSubtitle: values.deckSubtitle,
          audience: values.audience?.trim(),
          objective: values.objective?.trim() || selectedCard?.objective_hint || '',
          themeId: values.themeId,
          lengthOption: values.lengthOption || selectedCard?.length_option || 'medium',
          keyPoints: normalizeKeyPoints(values.keyPointsText || ''),
          generalRequirements: values.generalRequirements?.trim(),
          styleHint: values.styleHint?.trim() || selectedCard?.style_hint || '',
          specialRequirements: values.specialRequirements?.trim(),
          selectedCard: selectedCard
            ? {
                card_id: selectedCard.card_id,
                card_type: selectedCard.card_type,
                preset_key: selectedCard.preset_key,
                recommendation_type: selectedCard.recommendation_type,
              }
            : null,
        },
      });
      const nextDraftId = String((response.draft as any)?.draft_id || '').trim();
      const outline = findOutlineContent(response);
      setDraftId(nextDraftId);
      setOutlineText(outline ? JSON.stringify(outline, null, 2) : '');
      setEntryState('outline_ready');
    } catch (error) {
      if (error instanceof Error) {
        setErrorText(error.message);
      }
      setEntryState('error');
    }
  };

  const handleGenerate = async () => {
    if (!draftId) {
      message.warning('请先生成大纲。');
      return;
    }

    setEntryState('generating');
    try {
      let parsedOutline: Record<string, unknown> | undefined;
      if (outlineText.trim()) {
        parsedOutline = JSON.parse(outlineText);
      }
      await onSubmitGenerate({ draftId, outline: parsedOutline });
      setEntryState('idle');
      setDraftId('');
      setOutlineText('');
      onCancel();
    } catch (error) {
      const nextError = error instanceof Error ? error.message : 'PPT 生成失败';
      setErrorText(nextError);
      setEntryState('error');
    }
  };

  const renderCards = (items: PptEntryCard[]) => (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: 12,
      }}
    >
      {items.map((card) => {
        const active = selectedCard?.card_id === card.card_id;
        return (
          <Card
            key={card.card_id}
            hoverable
            size="small"
            onClick={() => applyCardDefaults(card)}
            style={{
              borderRadius: 12,
              borderColor: active ? '#1677ff' : undefined,
              boxShadow: active ? '0 0 0 1px rgba(22,119,255,0.16)' : undefined,
            }}
          >
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                <Text strong>{card.title}</Text>
                {card.length_option ? <Text type="secondary">{card.length_option}</Text> : null}
              </Space>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {card.description}
              </Paragraph>
            </Space>
          </Card>
        );
      })}
    </div>
  );

  return (
    <Modal title="创建 PPT" open={open} onCancel={onCancel} footer={null} width={920} destroyOnClose>
      <Space direction="vertical" size={18} style={{ width: '100%' }}>
        {!selectedDocIds.length ? <Alert type="warning" showIcon message="请先选择至少一份知识库文档。" /> : null}
        {errorText ? <Alert type="warning" showIcon message={errorText} /> : null}

        <Text type="secondary">
          当前已选文档：{selectedDocIds.length} 份{courseId ? `，课程 ${courseId}` : ''}
        </Text>

        {entryState === 'cards_loading' ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Skeleton active paragraph={{ rows: 3 }} />
            <Skeleton active paragraph={{ rows: 3 }} />
          </Space>
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
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

        <Form form={form} layout="vertical" initialValues={getInitialFormValues()}>
          <Form.Item name="deckTitle" label="PPT 标题" rules={[{ required: true, message: '请输入 PPT 标题' }]}>
            <Input placeholder="例如：AI Agent 中的 Skills 与 MCP" />
          </Form.Item>

          <Form.Item name="deckSubtitle" label="副标题">
            <Input placeholder="可选，用于补充课程或汇报场景" />
          </Form.Item>

          <Form.Item name="lengthOption" label="长度" rules={[{ required: true, message: '请选择长度' }]}>
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              options={[
                { label: '短篇', value: 'short' },
                { label: '标准', value: 'medium' },
                { label: '长篇', value: 'long' },
              ]}
            />
          </Form.Item>

          <Form.Item name="themeId" label="主题模板">
            <Select
              options={[
                { value: 'heu_academic_elegant', label: '学院典雅' },
                { value: 'heu_academic_basic', label: '学院基础' },
              ]}
            />
          </Form.Item>

          <Form.Item name="audience" label="受众">
            <Input placeholder="可直接填写，例如：高中生 / 本科生 / 教师培训" />
          </Form.Item>

          <Form.Item name="objective" label="汇报目标">
            <Select
              allowClear
              placeholder="可选；不填时会参考所选 PPT 卡片和通用要求提取"
              options={[
                { label: '课堂讲解', value: '课堂讲解' },
                { label: '主题分享', value: '主题分享' },
                { label: '对比分析', value: '对比分析' },
                { label: '汇报答辩', value: '汇报答辩' },
              ]}
            />
          </Form.Item>

          <Form.Item name="keyPointsText" label="重点内容">
            <TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder="一行一个重点，例如：定义、工作流程、典型案例" />
          </Form.Item>

          <Form.Item name="generalRequirements" label="通用配置">
            <TextArea
              autoSize={{ minRows: 3, maxRows: 6 }}
              placeholder="例如：受众为高中生，用于课堂讲解，希望语气更通俗，强调定义和案例。系统会在生成大纲前提取其中的受众、目标、长度和重点。"
            />
          </Form.Item>

          <Form.Item name="styleHint" label="表达风格">
            <Input placeholder="例如：讲解清晰、结论先行、适合课堂投屏" />
          </Form.Item>

          <Form.Item name="specialRequirements" label="补充约束">
            <TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="例如：避免过度术语化；最后一页只保留汇报人和学校" />
          </Form.Item>
        </Form>

        {entryState === 'outline_ready' ? (
          <div>
            <Title level={5}>大纲草稿</Title>
            <TextArea
              value={outlineText}
              onChange={(event) => setOutlineText(event.target.value)}
              autoSize={{ minRows: 12, maxRows: 20 }}
            />
          </div>
        ) : null}

        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Button onClick={onCancel} disabled={submitting}>
            取消
          </Button>
          <Space>
            <Button onClick={handleBuildOutline} loading={submitting || entryState === 'outline_loading'}>
              生成大纲
            </Button>
            <Button
              type="primary"
              onClick={handleGenerate}
              loading={submitting || entryState === 'generating'}
              disabled={entryState !== 'outline_ready'}
            >
              生成 PPT
            </Button>
          </Space>
        </Space>
      </Space>
    </Modal>
  );
}
