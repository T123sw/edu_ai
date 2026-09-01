import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const reportPreview = readFileSync(new URL('../../src/components/teacher/ReportArtifactPreview.tsx', import.meta.url), 'utf8');
const reportPreviewCss = readFileSync(new URL('../../src/components/teacher/ReportArtifactPreview.css', import.meta.url), 'utf8');

assert.match(
  studioPanel,
  /import\s+ReportArtifactPreview\s+from\s+['"]\.\/ReportArtifactPreview['"]/,
  'StudioPanel should use the structured report artifact preview component',
);

assert.match(
  studioPanel,
  /<ReportArtifactPreview[\s\S]*outlineContent=\{rawReportOutlineContent\}[\s\S]*onGenerateFromOutline=/,
  'Report preview should receive outline content and keep outline-to-body generation action',
);

assert.match(
  studioPanel,
  /const canToggleReportOutline = String\(\(viewingFile as any\)\?\.meta\?\.kind \|\| ''\)\.trim\(\) !== 'outline'/,
  'Report body preview should keep the body-outline switch even when outline content must be derived',
);

assert.match(
  reportPreview,
  /function\s+normalizeReportContent\(/,
  'Report preview should normalize markdown, JSON strings, and object payloads before rendering',
);

assert.match(
  reportPreview,
  /tryParseJson\(/,
  'Report preview should parse JSON string artifacts instead of showing raw JSON',
);

assert.match(
  reportPreview,
  /kind:\s*'outline'/,
  'Report preview should render report outlines as structured outlines',
);

assert.match(
  reportPreview,
  /outlineFromMarkdown\(/,
  'Report preview should derive an outline from markdown headings when no separate outline artifact is available',
);

assert.match(
  reportPreview,
  /report-artifact-preview__add-chat/,
  'Add-to-chat action should use a dedicated subtle button class',
);

assert.match(
  reportPreviewCss,
  /\.report-artifact-preview__document/,
  'Report preview should have a dedicated document reading layout',
);

assert.match(
  reportPreviewCss,
  /\.report-artifact-preview__add-chat\.ant-btn/,
  'Add-to-chat action should be styled as a quieter secondary action',
);

console.log('studioPanel.report-artifact-preview tests passed');
