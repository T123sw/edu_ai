import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  type ChatConversationReference,
  type ChatReplyRequestV2,
  buildChatReplyPayload,
} from '../../src/services/teacher/chatV2.ts';

const reference: ChatConversationReference = {
  conversation_id: 'conv-ref-1',
  title: '高一物理课堂观察',
  message_count: 6,
};

const storeFile = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');
const chatPanelFile = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(storeFile, /conversationReference:\s*ConversationReference \| null;/, 'store should expose conversationReference state');
assert.match(storeFile, /setConversationReference:\s*\(reference:\s*ConversationReference \| null\)\s*=>\s*void;/, 'store should expose setConversationReference action');
assert.match(storeFile, /clearConversationReference:\s*\(\)\s*=>\s*void;/, 'store should expose clearConversationReference action');
assert.match(chatPanelFile, /setConversationReference\(\{[\s\S]*conversation_id:\s*item\.conversation_id/, 'ChatPanel should allow referencing a history conversation without switching to it');
assert.match(chatPanelFile, /conversationReference\s*,/, 'ChatPanel should read conversationReference from the store');
assert.match(chatPanelFile, /clearConversationReference\(\)/, 'ChatPanel should allow clearing a referenced conversation');

const payload = buildChatReplyPayload({
  question: '基于我引用的历史对话继续分析',
  conversationId: 'conv-current',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: ['doc-1'],
  artifactReference: null,
  conversationReference: reference,
});

assert.deepEqual(payload, {
  question: '基于我引用的历史对话继续分析',
  conversation_id: 'conv-current',
  course_id: 'course-1',
  allow_rag: false,
  allow_web: false,
  selected_doc_ids: ['doc-1'],
  conversation_reference: {
    conversation_id: 'conv-ref-1',
    title: '高一物理课堂观察',
    message_count: 6,
  },
} satisfies ChatReplyRequestV2);

console.log('chatPanel.conversation-reference tests passed');
