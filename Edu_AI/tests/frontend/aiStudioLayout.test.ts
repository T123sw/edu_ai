import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const aiStudioPageFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url),
  'utf8',
);

assert.match(
  aiStudioPageFile,
  /当前课程/,
  'AiStudioPage should render a visible 当前课程 label in the top context bar',
);

assert.match(
  aiStudioPageFile,
  /当前知识点/,
  'AiStudioPage should render a visible 当前知识点 label in the top context bar',
);

assert.match(
  aiStudioPageFile,
  /ai-studio-context-bar/,
  'AiStudioPage should render the context bar shell class before the three-column workspace',
);

assert.match(
  aiStudioPageFile,
  /getAiStudioCourseLabel/,
  'AiStudioPage should use the page-scoped course label helper',
);

assert.match(
  aiStudioPageFile,
  /getAiStudioKnowledgePointLabel/,
  'AiStudioPage should use the page-scoped knowledge point label helper',
);

console.log('aiStudioLayout tests passed');
