import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/PptEntryPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /fetchPptEntryCardsV2\(/, 'PptEntryPanel should load PPT recommendation cards');
assert.match(file, /lengthOption/, 'PptEntryPanel should expose an explicit length option');
assert.match(file, /generalRequirements/, 'PptEntryPanel should support general requirements for structured extraction');
assert.match(file, /selectedCard/, 'PptEntryPanel should track PPT recommendation card selection');
assert.doesNotMatch(file, /promptDraft/, 'PptEntryPanel should not reuse report prompt drafting');

console.log('pptEntryPanel tests passed');
