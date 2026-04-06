import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync('d:/github/edu_ai/Edu_AI/src/components/teacher/ChatPanel.tsx', 'utf8');

assert.match(
  file,
  /const restoredFiles = restoreGeneratedFilesFromConversationDetail\(detail\);[\s\S]*setViewingFile\(null\);/,
  'restoring generated files should keep preview collapsed after refresh',
);
assert.doesNotMatch(
  file,
  /setViewingFile\(restoredFiles\.length > 0 \? restoredFiles\[restoredFiles\.length - 1\] : null\);/,
  'restoring generated files must not auto-open the latest file',
);

console.log('chatPanel.restore-preview tests passed');
