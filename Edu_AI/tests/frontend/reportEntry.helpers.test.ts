import assert from 'node:assert/strict';

import {
  buildKnowledgeBaseReportRequest,
  createDraftCacheKey,
  getDefaultPresetCards,
  groupReportEntryCards,
  shouldConfirmCardSwitch,
} from '../../src/services/teacher/reportEntry.helpers.ts';

const presets = getDefaultPresetCards();
assert.deepEqual(
  presets.map((card) => card.card_id),
  ['preset-brief', 'preset-detailed', 'preset-study-plan', 'preset-custom'],
);

const grouped = groupReportEntryCards([
  presets[0],
  {
    card_id: 'rec-summary',
    card_type: 'recommended',
    title: '核心内容总结',
    description: '总结重点',
    prompt_draft: '请总结重点',
    recommendation_type: 'summary',
  },
]);

assert.equal(grouped.presets.length, 1);
assert.equal(grouped.recommended.length, 1);
assert.equal(createDraftCacheKey(presets[0]), 'preset-brief');

const payload = buildKnowledgeBaseReportRequest({
  question: '最终文本',
  promptDraft: '默认文本',
  card: presets[0],
  courseId: 'course-1',
  selectedDocIds: ['doc-1'],
  allowRag: false,
  allowWeb: false,
});

assert.equal(payload.entry_mode, undefined);
assert.equal(payload.final_user_prompt, '最终文本');
assert.equal(payload.question, '最终文本');
assert.equal(payload.prompt_draft, '默认文本');
assert.equal(payload.selected_card?.preset_key, 'brief');
assert.equal((payload.report_config?.source_scope as string), 'selected_documents_only');
assert.equal(payload.entry_mode, undefined);

assert.equal(shouldConfirmCardSwitch({ currentCardId: 'a', nextCardId: 'b', draftDirty: true }), true);
assert.equal(shouldConfirmCardSwitch({ currentCardId: 'a', nextCardId: 'a', draftDirty: true }), false);
assert.equal(shouldConfirmCardSwitch({ currentCardId: 'a', nextCardId: 'b', draftDirty: false }), false);

console.log('reportEntry.helpers tests passed');
