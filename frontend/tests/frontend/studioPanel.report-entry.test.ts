import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
const reportEntryModal = readFileSync(new URL('../../src/components/teacher/ReportEntryModal.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /import\s+ReportEntryModal\s+from\s+['"]\.\/ReportEntryModal['"]/, 'StudioPanel should use the dedicated report entry modal');
assert.match(studioPanel, /if\s*\(type\s*===\s*'report'\)\s*\{[\s\S]*setReportEntryVisible\(true\)/, 'StudioPanel should open the report entry modal for report generation');
assert.match(studioPanel, /buildKnowledgeBaseReportRequest\(/, 'StudioPanel should build a knowledge-base report payload');
assert.match(studioPanel, /generateKnowledgeBaseReportV2\(/, 'StudioPanel should call the dedicated knowledge-base direct report API');
assert.doesNotMatch(studioPanel, /sendReportV2\(\s*buildKnowledgeBaseReportRequest/, 'StudioPanel should no longer send knowledge-base reports through the chat report workflow');
assert.match(studioPanel, /<ReportEntryModal/, 'StudioPanel should render the report entry modal');

assert.match(reportEntryModal, /fetchReportEntryCardsV2\(/, 'ReportEntryModal should load entry cards from the backend');
assert.match(reportEntryModal, /entryState === 'editing_prompt'/, 'ReportEntryModal should support the editor state');
assert.doesNotMatch(reportEntryModal, /language/i, 'ReportEntryModal should not expose a language selector in the first version');

console.log('studioPanel.report-entry tests passed');
