import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanelFile = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  chatPanelFile,
  /const conversationMatchesCurrentWorkspace = useMemo/,
  'ChatPanel should define a helper for checking whether a history conversation belongs to the current workspace scope',
);

assert.match(
  chatPanelFile,
  /conversationMatchesCurrentWorkspace\(storedConversation\)/,
  'ChatPanel should only auto-restore the stored conversation when it matches the current workspace',
);

assert.match(
  chatPanelFile,
  /const initialConversation = list\.find\(\(item\) => conversationMatchesCurrentWorkspace\(item\)\);/,
  'ChatPanel should auto-open only a history conversation that belongs to the current workspace',
);

assert.doesNotMatch(
  chatPanelFile,
  /else if \(list\.length > 0\) \{\s*setCurrentConversationId\(list\[0\]\.conversation_id\);\s*await loadConversation\(list\[0\]\.conversation_id, false\);/,
  'ChatPanel should not blindly auto-open the first history conversation across scopes',
);

console.log('chatPanel.workspace-scope-restoration tests passed');
