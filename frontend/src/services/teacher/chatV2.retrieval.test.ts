import assert from 'node:assert/strict';
import test from 'node:test';

import { buildChatReplyPayload, resolveChatRetrievalDocIds } from './chatV2';

test('checked documents remain the retrieval scope without the full knowledge-base toggle', () => {
  assert.deepEqual(
    resolveChatRetrievalDocIds({
      mountFullKnowledgeBase: false,
      selectedDocIds: ['doc-selected'],
      scopedDocIds: ['doc-selected', 'doc-other'],
    }),
    ['doc-selected'],
  );
});

test('checked documents remain authoritative when knowledge retrieval is enabled', () => {
  assert.deepEqual(
    resolveChatRetrievalDocIds({
      mountFullKnowledgeBase: true,
      selectedDocIds: ['doc-selected'],
      scopedDocIds: ['doc-selected', 'doc-other'],
    }),
    ['doc-selected'],
  );
});

test('checked documents enable selected-document retrieval in the chat payload', () => {
  const payload = buildChatReplyPayload({
    question: '链表如何实现',
    allowRag: false,
    allowWeb: false,
    selectedDocIds: ['doc-selected'],
  });

  assert.equal(payload.allow_rag, true);
  assert.equal(payload.source_mode, 'selected_documents');
  assert.deepEqual(payload.selected_doc_ids, ['doc-selected']);
});

test('knowledge retrieval without checked documents uses course-auto mode', () => {
  const payload = buildChatReplyPayload({
    question: '链表如何实现',
    allowRag: true,
    allowWeb: false,
    selectedDocIds: [],
  });

  assert.equal(payload.source_mode, 'course_auto');
  assert.deepEqual(payload.selected_doc_ids, []);
});

test('chat does not use knowledge when neither selection nor retrieval is enabled', () => {
  const payload = buildChatReplyPayload({
    question: '链表如何实现',
    allowRag: false,
    allowWeb: false,
    selectedDocIds: [],
  });

  assert.equal(payload.source_mode, 'none');
  assert.equal(payload.allow_rag, false);
});
