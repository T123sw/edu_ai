import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const materialsCss = readFileSync(new URL('../../src/pages/teacher/CourseMaterialsPage.css', import.meta.url), 'utf8');
const knowledgeBaseCss = readFileSync(new URL('../../src/pages/KnowledgeBasePage.css', import.meta.url), 'utf8');
const knowledgeGraphCss = readFileSync(new URL('../../src/pages/teacher/KnowledgeGraphPage.css', import.meta.url), 'utf8');
const materialsPage = readFileSync(new URL('../../src/pages/teacher/CourseMaterialsPage.tsx', import.meta.url), 'utf8');
const knowledgeGraphPage = readFileSync(new URL('../../src/pages/teacher/KnowledgeGraphPage.tsx', import.meta.url), 'utf8');

assert.match(
  materialsCss,
  /linear-gradient\(/,
  'Course materials page should adopt the upgraded gradient shell styling',
);

assert.match(
  materialsCss,
  /border-radius:\s*28px/,
  'Course materials page cards should use the larger stitched surface radius',
);

assert.match(
  materialsPage,
  /className="course-materials-page"/,
  'Course materials page should keep the main shell class for the upgraded resource styling',
);

assert.match(
  knowledgeBaseCss,
  /box-shadow:\s*0 20px 44px/,
  'Knowledge base page should use the stitched glass-card shadow scale',
);

assert.match(
  knowledgeBaseCss,
  /border-radius:\s*24px/,
  'Knowledge base page should adopt the rounded stitched card language',
);

assert.match(
  knowledgeGraphCss,
  /backdrop-filter:\s*blur/,
  'Knowledge graph detail panel should use the upgraded glass backdrop styling',
);

assert.match(
  knowledgeGraphCss,
  /linear-gradient\(135deg,\s*#0f172a/,
  'Knowledge graph should use the darker stitched gradient panel treatment',
);

assert.match(
  knowledgeGraphPage,
  /className="details-card"/,
  'Knowledge graph page should keep the detail card hook used by the upgraded styling',
);

console.log('resource-shell-style-integration tests passed');
