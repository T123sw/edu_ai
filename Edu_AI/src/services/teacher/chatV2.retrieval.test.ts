import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveChatRetrievalDocIds } from './chatV2';

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

test('the full knowledge-base toggle mounts all documents in the current scope', () => {
  assert.deepEqual(
    resolveChatRetrievalDocIds({
      mountFullKnowledgeBase: true,
      selectedDocIds: ['doc-selected'],
      scopedDocIds: ['doc-selected', 'doc-other'],
    }),
    ['doc-selected', 'doc-other'],
  );
});
