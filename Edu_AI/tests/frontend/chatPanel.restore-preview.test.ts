import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(
  file,
  /const restoredFiles = restoreGeneratedFilesFromConversationDetail\(detail\);[\s\S]*replaceConversationGeneratedFiles\(restoredFiles\);[\s\S]*setViewingFile\(null\);/,
  'restoring generated files should replace conversation-scoped files and keep preview collapsed after refresh',
);
assert.doesNotMatch(
  file,
  /setViewingFile\(restoredFiles\.length > 0 \? restoredFiles\[restoredFiles\.length - 1\] : null\);/,
  'restoring generated files must not auto-open the latest file',
);
assert.match(
  file,
  /const handleNewConversation = \(\) => \{[\s\S]*clearConversationGeneratedFiles\(\);[\s\S]*setViewingFile\(null\);/,
  'starting a new conversation should clear conversation-scoped generated files and preview',
);

console.log('chatPanel.restore-preview tests passed');
