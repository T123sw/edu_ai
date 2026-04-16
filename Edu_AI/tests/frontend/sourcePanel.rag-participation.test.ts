import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const sourcePanel = readFileSync(new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url), 'utf8');

assert.doesNotMatch(
  sourcePanel,
  /Switch/,
  'SourcePanel should not render a second per-document RAG switch',
);

assert.doesNotMatch(
  sourcePanel,
  /updateDocumentParticipation\(/,
  'SourcePanel should not call a separate RAG participation endpoint from the document list',
);

assert.match(
  sourcePanel,
  /const allFileKeys = fileList\.map\(file => file\.key\);/,
  'SourcePanel select-all should keep using the document checkbox as the only participation control',
);

assert.match(
  sourcePanel,
  /<Checkbox checked=\{checkedKeys\.includes\(file\.key\)\} onChange=/,
  'SourcePanel should keep the document checkbox as the per-conversation RAG participation control',
);

console.log('sourcePanel.rag-participation tests passed');
