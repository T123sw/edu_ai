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
  /selectedDocs\.length > 0 \? selectedDocs : scopedSourceDocIds/,
  'ChatPanel should use visible scoped documents as the default RAG document set when nothing is manually selected',
);

console.log('chatPanel.scoped-default-docs tests passed');
