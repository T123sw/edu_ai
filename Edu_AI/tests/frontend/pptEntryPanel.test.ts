import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/PptEntryPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /fetchPptEntryCardsV2\(/, 'PptEntryPanel should load PPT recommendation cards');
assert.match(file, /default_selected_card_id/, 'PptEntryPanel should read the backend default card');
assert.match(file, /pickInitialPptEntryCard\(/, 'PptEntryPanel should use the shared initial-card helper');
assert.match(file, /buildPptEntryFormValuesFromCard\(/, 'PptEntryPanel should map card prefill into form values');
assert.match(file, /targetSlideCount/, 'PptEntryPanel should preserve hidden target slide count');
assert.match(file, /selectedCard/, 'PptEntryPanel should track PPT recommendation card selection');
assert.match(file, /setEntryState\('cards_loading'\);[\s\S]*clearDraftState\(\);/, 'PptEntryPanel should clear stale draft state when a new load cycle starts');
assert.match(file, /setCards\(DEFAULT_PPT_CARDS\);\s*clearDraftState\(\);[\s\S]*setEntryState\('cards_ready'\);/, 'PptEntryPanel should clear stale draft state after a fetch failure');
assert.doesNotMatch(file, /objective: values\.objective\?\.trim\(\)\s*\|\|\s*selectedCard\?\.objective_hint/, 'PptEntryPanel should not reapply selected objective defaults');
assert.doesNotMatch(file, /lengthOption: values\.lengthOption\s*\|\|\s*selectedCard\?\.length_option/, 'PptEntryPanel should not reapply selected length defaults');
assert.doesNotMatch(file, /styleHint: values\.styleHint\?\.trim\(\)\s*\|\|\s*selectedCard\?\.style_hint/, 'PptEntryPanel should not reapply selected style defaults');
assert.doesNotMatch(file, /promptDraft/, 'PptEntryPanel should not reuse report prompt drafting');

console.log('pptEntryPanel tests passed');
