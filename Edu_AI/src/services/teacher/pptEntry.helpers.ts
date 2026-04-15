import type {
  KnowledgeBaseDirectPptGenerateRequestV2,
  KnowledgeBaseDirectPptOutlineRequestV2,
  PptEntryCard,
  PptEntryCardSelection,
} from './chatV2';

export interface DirectPptEntryConfigInput {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: 'short' | 'medium' | 'long';
  targetSlideCount?: number;
  keyPoints: string[];
  styleHint?: string;
  specialRequirements?: string;
  generalRequirements?: string;
  selectedCard?: PptEntryCardSelection | null;
}

export interface PptEntryFormValues {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: 'short' | 'medium' | 'long';
  targetSlideCount?: number;
  keyPointsText?: string;
  styleHint?: string;
  specialRequirements?: string;
  generalRequirements?: string;
}

export function pickInitialPptEntryCard(cards: PptEntryCard[], defaultSelectedCardId?: string | null): PptEntryCard | null {
  const normalizedDefaultCardId = String(defaultSelectedCardId || '').trim();
  return (
    cards.find((card) => card.card_id === normalizedDefaultCardId) ||
    cards.find((card) => card.card_type === 'recommended') ||
    cards.find((card) => card.card_type === 'preset') ||
    null
  );
}

export function buildPptEntryFormValuesFromCard(card: PptEntryCard): PptEntryFormValues {
  const prefill = card.prefill_config || {};
  return {
    deckTitle: prefill.deck_title || '',
    deckSubtitle: prefill.deck_subtitle || '',
    audience: prefill.audience || '',
    objective: prefill.objective || card.objective_hint || '',
    themeId: prefill.theme_id || 'heu_academic_elegant',
    lengthOption: prefill.length_option || card.length_option || 'medium',
    targetSlideCount: prefill.target_slide_count,
    keyPointsText: Array.isArray(prefill.key_points) ? prefill.key_points.join('\n') : '',
    styleHint: prefill.style_hint || card.style_hint || '',
    specialRequirements: prefill.special_requirements || '',
    generalRequirements: prefill.general_requirements || '',
  };
}

export function buildDirectPptOutlineRequest(options: {
  courseId?: string;
  selectedDocIds: string[];
  config: DirectPptEntryConfigInput;
}): KnowledgeBaseDirectPptOutlineRequestV2 {
  return {
    course_id: options.courseId,
    selected_doc_ids: options.selectedDocIds,
    ppt_config: {
      deck_title: options.config.deckTitle,
      deck_subtitle: options.config.deckSubtitle,
      audience: options.config.audience,
      objective: options.config.objective,
      theme_id: options.config.themeId,
      length_option: options.config.lengthOption,
      target_slide_count: options.config.targetSlideCount,
      key_points: options.config.keyPoints,
      style_hint: options.config.styleHint,
      special_requirements: options.config.specialRequirements,
      general_requirements: options.config.generalRequirements,
      selected_card: options.config.selectedCard || undefined,
    },
  };
}

export function buildDirectPptGenerateRequest(options: {
  draftId: string;
  outline?: Record<string, unknown>;
}): KnowledgeBaseDirectPptGenerateRequestV2 {
  return {
    draft_id: options.draftId,
    confirm: true,
    outline: options.outline,
  };
}
