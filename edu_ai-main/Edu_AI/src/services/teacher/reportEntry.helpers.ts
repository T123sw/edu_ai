import type { KnowledgeBaseDirectReportRequestV2, ReportEntryCard } from './chatV2';

export function getDefaultPresetCards(): ReportEntryCard[] {
  return [
    {
      card_id: 'preset-brief',
      card_type: 'preset',
      title: '简要报告',
      description: '快速提炼材料主旨、关键结论与核心依据。',
      prompt_draft: '请基于已选文档，生成一份中文简要报告，提炼核心主题、关键结论和主要依据，结构清晰，篇幅适中。',
      preset_key: 'brief',
    },
    {
      card_id: 'preset-detailed',
      card_type: 'preset',
      title: '详细报告',
      description: '完整梳理背景、分析过程、结论与建议。',
      prompt_draft: '请基于已选文档，生成一份中文详细报告，包含背景、核心内容、重点分析、结论与建议，并尽可能完整覆盖材料中的主要信息。',
      preset_key: 'detailed',
    },
    {
      card_id: 'preset-study-plan',
      card_type: 'preset',
      title: '学习方案',
      description: '将材料整理成可执行的学习目标与学习路径。',
      prompt_draft: '请基于已选文档，生成一份中文学习方案，包含学习目标、重点难点、学习顺序、阶段安排和实践任务，强调可执行性。',
      preset_key: 'study_plan',
    },
    {
      card_id: 'preset-custom',
      card_type: 'preset',
      title: '自定义报告',
      description: '保留自由表达空间，围绕你的补充要求生成报告。',
      prompt_draft: '请基于已选文档，生成一份中文报告，并根据我后续补充的要求组织结构与内容，避免脱离文档空泛发挥。',
      preset_key: 'custom',
    },
  ];
}

export function groupReportEntryCards(cards: ReportEntryCard[]): {
  presets: ReportEntryCard[];
  recommended: ReportEntryCard[];
} {
  const presets = cards.filter((card) => card.card_type === 'preset');
  const recommended = cards.filter((card) => card.card_type === 'recommended');
  return { presets, recommended };
}

export function createDraftCacheKey(card: Pick<ReportEntryCard, 'card_id'>): string {
  return String(card.card_id || '').trim();
}

export function shouldConfirmCardSwitch(options: {
  currentCardId?: string | null;
  nextCardId?: string | null;
  draftDirty: boolean;
}): boolean {
  const currentCardId = String(options.currentCardId || '').trim();
  const nextCardId = String(options.nextCardId || '').trim();
  if (!options.draftDirty) {
    return false;
  }
  if (!currentCardId || !nextCardId) {
    return false;
  }
  return currentCardId !== nextCardId;
}

export function buildKnowledgeBaseReportRequest(options: {
  question: string;
  promptDraft: string;
  card: ReportEntryCard;
  courseId?: string;
  selectedDocIds: string[];
  allowRag: boolean;
  allowWeb: boolean;
}): KnowledgeBaseDirectReportRequestV2 {
  return {
    question: options.question,
    course_id: options.courseId,
    selected_doc_ids: options.selectedDocIds,
    prompt_draft: options.promptDraft,
    final_user_prompt: options.question,
    selected_card: {
      card_id: options.card.card_id,
      card_type: options.card.card_type,
      preset_key: options.card.preset_key,
      recommendation_type: options.card.recommendation_type,
    },
    report_config: {
      source_scope: 'selected_documents_only',
    },
  };
}
