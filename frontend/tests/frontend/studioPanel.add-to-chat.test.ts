import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.doesNotMatch(file, /key:\s*'add-to-chat'/, 'StudioPanel should not expose add-to-chat in the list item menu');
assert.match(file, /viewingFile\.type === 'report'[\s\S]*添加到对话/, 'StudioPanel should expose add-to-chat inside the report preview detail');
assert.match(file, /setArtifactReference\(/, 'StudioPanel should write artifact references into the store');
assert.match(file, /isArtifactReferenceEligible\(viewingFile\)/, 'StudioPanel should only expose add-to-chat for eligible previewed report artifacts');

console.log('studioPanel.add-to-chat tests passed');
