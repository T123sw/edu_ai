import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(
  new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url),
  'utf8',
);

assert.match(
  file,
  /getKnowledgeBaseDocuments/,
  'stitch knowledge graph should load the selected node course knowledge-base documents',
);

assert.match(
  file,
  /uploadKnowledgeBaseDocument/,
  'stitch knowledge graph should reuse the shared course knowledge-base upload API',
);

assert.match(
  file,
  /handleKnowledgeBaseUpload/,
  'stitch knowledge graph should define a dedicated selected-node upload handler',
);

assert.match(
  file,
  /scopeType:\s*isCourseRootNode \? "course" : "knowledge_point"/,
  'stitch knowledge graph should upload to course scope for the root and knowledge-point scope for normal nodes',
);

assert.match(
  file,
  /scopeId:\s*isCourseRootNode \? undefined : targetNode\.id/,
  'stitch knowledge graph should omit scopeId when uploading to the course root scope',
);

assert.match(
  file,
  /libraryType:\s*"course"/,
  'stitch knowledge graph should always upload into the formal course knowledge base',
);

assert.match(
  file,
  /knowledgeBaseUploadInputRef/,
  'stitch knowledge graph should expose a real file-input trigger in the node detail panel',
);

assert.match(
  file,
  /导入到本知识点知识库|导入到课程总知识库/,
  'stitch knowledge graph should show an explicit upload button in the node detail panel',
);

console.log('knowledgeGraph.node-course-kb-upload tests passed');
