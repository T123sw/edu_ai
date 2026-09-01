import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const typesFile = readFileSync(
  new URL('../../src/stitch/api/types.ts', import.meta.url),
  'utf8',
);
const apiFile = readFileSync(
  new URL('../../src/stitch/api/courses.ts', import.meta.url),
  'utf8',
);
const graphPageFile = readFileSync(
  new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url),
  'utf8',
);

assert.match(
  typesFile,
  /export type KnowledgeGraphTextbookImportResponse/,
  'stitch types should define the textbook import response',
);

assert.match(
  apiFile,
  /export function importKnowledgeGraphTextbook/,
  'stitch API should expose a textbook import helper',
);

assert.match(
  apiFile,
  /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/textbook-import/,
  'stitch API helper should call the textbook import route',
);

assert.match(
  graphPageFile,
  /importKnowledgeGraphTextbook/,
  'stitch KnowledgeGraphPage should call the dedicated textbook import helper',
);

assert.match(
  graphPageFile,
  /fileInputRef/,
  'stitch KnowledgeGraphPage should expose a hidden file input for course-level textbook import',
);

assert.match(
  graphPageFile,
  /setImporting\(/,
  'stitch KnowledgeGraphPage should track textbook import loading state',
);

assert.match(
  graphPageFile,
  /applyGraphToCanvas\(result\.knowledge_graph\.root\)/,
  'stitch KnowledgeGraphPage should rebuild the graph from the textbook import response',
);

console.log('stitchKnowledgeGraph.textbook-import tests passed');
