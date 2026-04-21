import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const apiFile = readFileSync(
  new URL('../../src/services/teacher/api.ts', import.meta.url),
  'utf8',
);
const graphPageFile = readFileSync(
  new URL('../../src/pages/teacher/KnowledgeGraphPage.tsx', import.meta.url),
  'utf8',
);

assert.match(
  apiFile,
  /export interface TextbookKnowledgeGraphImportResponse/,
  'teacher API should define a textbook import response type',
);

assert.match(
  apiFile,
  /export const importTextbookKnowledgeGraph = async/,
  'teacher API should expose a textbook knowledge graph import helper',
);

assert.match(
  apiFile,
  /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/textbook-import/,
  'teacher API helper should call the dedicated textbook import route',
);

assert.match(
  graphPageFile,
  /importTextbookKnowledgeGraph/,
  'KnowledgeGraphPage should call the dedicated textbook import helper',
);

assert.match(
  graphPageFile,
  /textbookImportInputRef/,
  'KnowledgeGraphPage should expose a hidden file input for textbook import',
);

assert.match(
  graphPageFile,
  /setImportingTextbookKnowledgeGraph/,
  'KnowledgeGraphPage should track a loading state while textbook import runs',
);

assert.match(
  graphPageFile,
  /result\.knowledge_graph\.root/,
  'KnowledgeGraphPage should refresh the graph from the textbook import response',
);

console.log('knowledgeGraph.textbook-import tests passed');
