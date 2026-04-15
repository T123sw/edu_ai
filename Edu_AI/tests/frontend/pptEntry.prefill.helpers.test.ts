import assert from 'node:assert/strict';

import * as helpers from '../../src/services/teacher/pptEntry.helpers.ts';

const cards = [
  {
    card_id: 'preset-knowledge-lecture',
    card_type: 'preset',
    title: 'Knowledge lecture',
    description: 'Lecture style deck',
    objective_hint: '课堂讲解',
    length_option: 'medium',
    style_hint: '逻辑清晰',
    prefill_config: {
      deck_title: 'AI Agent Core Concepts',
      deck_subtitle: 'From rules to reasoning',
      audience: 'Undergraduate students',
      objective: '课堂讲解',
      theme_id: 'heu_academic_elegant',
      length_option: 'long',
      target_slide_count: 16,
      key_points: ['Definition', 'Examples'],
      style_hint: '突出概念结构',
      special_requirements: 'Keep it concise',
      general_requirements: 'Focus on examples',
    },
  },
  {
    card_id: 'rec-concept-focus',
    card_type: 'recommended',
    title: 'Recommended concept focus',
    description: 'Recommended card',
    objective_hint: '主题分享',
    length_option: 'short',
  },
] as const;

const outOfOrderCards = [
  {
    card_id: 'unrelated-intro',
    card_type: 'preset',
    title: 'Unrelated intro',
    description: 'Should not win by position',
    objective_hint: '涓嶅簲璇ュ叆閫?',
    length_option: 'short',
  },
  cards[0],
  cards[1],
] as const;

assert.equal(typeof helpers.pickInitialPptEntryCard, 'function');
assert.equal(typeof helpers.buildPptEntryFormValuesFromCard, 'function');

assert.equal(
  helpers.pickInitialPptEntryCard(cards as any, 'rec-concept-focus')?.card_id,
  'rec-concept-focus',
);
assert.equal(helpers.pickInitialPptEntryCard(cards as any, 'missing')?.card_id, 'rec-concept-focus');
assert.equal(helpers.pickInitialPptEntryCard([cards[0]] as any, 'missing')?.card_id, 'preset-knowledge-lecture');
assert.equal(helpers.pickInitialPptEntryCard(outOfOrderCards as any, 'missing')?.card_id, 'rec-concept-focus');
assert.equal(helpers.pickInitialPptEntryCard([], 'missing'), null);

assert.deepEqual(helpers.buildPptEntryFormValuesFromCard(cards[0] as any), {
  deckTitle: 'AI Agent Core Concepts',
  deckSubtitle: 'From rules to reasoning',
  audience: 'Undergraduate students',
  objective: '课堂讲解',
  themeId: 'heu_academic_elegant',
  lengthOption: 'long',
  targetSlideCount: 16,
  keyPointsText: 'Definition\nExamples',
  styleHint: '突出概念结构',
  generalRequirements: 'Focus on examples',
  specialRequirements: 'Keep it concise',
});

assert.deepEqual(
  helpers.buildPptEntryFormValuesFromCard(
    {
      card_id: 'fallback-card',
      card_type: 'preset',
      title: 'Fallback',
      description: 'Fallback',
      objective_hint: '课堂讲解',
      length_option: 'medium',
      style_hint: '清晰表达',
    } as any,
  ),
  {
    deckTitle: '',
    deckSubtitle: '',
    audience: '',
    objective: '课堂讲解',
    themeId: 'heu_academic_elegant',
    lengthOption: 'medium',
    targetSlideCount: undefined,
    keyPointsText: '',
    styleHint: '清晰表达',
    generalRequirements: '',
    specialRequirements: '',
  },
);

console.log('pptEntry.prefill.helpers tests passed');
