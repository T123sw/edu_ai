import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const chatPanel = readFileSync(
  new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url),
  'utf8',
);

const store = readFileSync(
  new URL('../../src/store/teacher/useStore.ts', import.meta.url),
  'utf8',
);

assert.match(
  store,
  /scopedSourceDocIds:\s*string\[\]/,
  'teacher store should keep the document ids visible in the current workspace scope',
);

assert.match(
  store,
  /setScopedSourceDocIds:\s*\(ids:\s*string\[\]\) => void/,
  'teacher store should expose a setter for scoped source document ids',
);

assert.match(
  chatPanel,
  /scopedSourceDocIds/,
  'ChatPanel should read scoped source document ids from the store',
);

assert.match(
  chatPanel,
  /resolveChatRetrievalDocIds\(\{[\s\S]*selectedDocIds: selectedDocs,[\s\S]*scopedDocIds: scopedSourceDocIds/,
  'ChatPanel should use the shared retrieval policy, which keeps explicit personal selections separate from automatic course retrieval',
);

console.log('chatPanel.scoped-default-docs tests passed');
