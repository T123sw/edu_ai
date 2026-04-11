import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /import\s+PptEntryPanel\s+from\s+['"]\.\/PptEntryPanel['"]/);
assert.match(studioPanel, /if\s*\(type\s*===\s*'ppt'\)\s*\{[\s\S]*setPptEntryVisible\(true\)/);
assert.match(studioPanel, /title="PPT"/);
assert.match(studioPanel, /generateKnowledgeBasePptOutlineV2\(/);
assert.match(studioPanel, /generateKnowledgeBasePptV2\(/);
assert.match(studioPanel, /<PptEntryPanel/);
assert.doesNotMatch(studioPanel, /title="Report"/);

console.log('studioPanel.ppt-entry tests passed');
