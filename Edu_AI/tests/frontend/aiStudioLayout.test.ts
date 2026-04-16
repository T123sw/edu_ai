import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const aiStudioPageFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url),
  'utf8',
);

const aiStudioCssFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.css', import.meta.url),
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

assert.match(
  aiStudioCssFile,
  /\.ai-studio-shell/,
  'AiStudioPage.css should define the outer studio shell',
);

assert.match(
  aiStudioCssFile,
  /\.ai-workspace-shell/,
  'AiStudioPage.css should define the dedicated workspace shell wrapper',
);

assert.match(
  aiStudioCssFile,
  /\.ai-studio-context-bar/,
  'AiStudioPage.css should style the top context bar',
);

assert.match(
  aiStudioCssFile,
  /\.ai-workspace-shell__frame/,
  'AiStudioPage.css should style the layered workbench frame',
);

assert.match(
  aiStudioCssFile,
  /radial-gradient\(circle at top/,
  'AiStudioPage.css should introduce a subtle layered background for the beautified shell',
);

assert.match(
  aiStudioCssFile,
  /background:\s*linear-gradient\(180deg,\s*#f4f6f8 0%,\s*#eef1f4 100%\)/,
  'AiStudioPage.css should use the calmer neutral page background',
);

assert.match(
  aiStudioCssFile,
  /box-shadow:\s*0 24px 60px/,
  'AiStudioPage.css should give the workbench frame a deeper but still restrained shadow',
);

assert.match(
  aiStudioCssFile,
  /border-radius:\s*18px/,
  'AiStudioPage.css should tighten panel corner radius for a more product-grade shell',
);

assert.doesNotMatch(
  aiStudioCssFile,
  /backdrop-filter:\s*blur/i,
  'AiStudioPage.css should remove the previous glassmorphism blur treatment',
);

console.log('aiStudioLayout tests passed');
