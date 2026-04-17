import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /if \(!currentConversationId \|\| workflowType !== 'ppt' \|\| workflowStatus !== 'running'\)/,
  'ChatPanel should track running PPT workflows before polling conversation detail',
);

assert.match(
  chatPanelFile,
  /setInterval\(\(\)\s*=>\s*\{\s*void loadConversation\(currentConversationId,\s*false,\s*true\);/s,
  'ChatPanel should silently poll conversation detail for running PPT edits',
);

assert.match(
  chatPanelFile,
  /const loadConversation = async \(\s*conversationId: string,\s*showSuccess = true,\s*silent = false\s*\)/,
  'ChatPanel should support a silent conversation reload mode for polling',
);

console.log('chatPanel.workflow-polling tests passed');
