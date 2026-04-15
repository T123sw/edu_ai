import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(
  file,
  /const restoredFiles = restoreGeneratedFilesFromConversationDetail\(detail\);[\s\S]*replaceConversationGeneratedFiles\(restoredFiles\);[\s\S]*if \(\s*silent\s*&&\s*nextWorkflowType === 'ppt'\s*&&\s*nextWorkflowStatus === 'completed'\s*&&\s*restoredFiles\.length > 0\s*\)\s*\{[\s\S]*setViewingFile\(restoredFiles\[restoredFiles\.length - 1\]\);[\s\S]*\}\s*else if \(!silent\)\s*\{[\s\S]*setViewingFile\(null\);[\s\S]*\}/,
  'restoring generated files should auto-open the latest PPT preview after silent polling completes, while normal history loads keep preview collapsed',
);
assert.match(
  file,
  /const handleNewConversation = \(\) => \{[\s\S]*clearConversationGeneratedFiles\(\);[\s\S]*setViewingFile\(null\);/,
  'starting a new conversation should clear conversation-scoped generated files and preview',
);

console.log('chatPanel.restore-preview tests passed');
