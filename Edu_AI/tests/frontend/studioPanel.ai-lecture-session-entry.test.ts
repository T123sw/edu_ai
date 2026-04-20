import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');
const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(store, /'ai_lecture_session'/, 'GeneratedFile should allow AI lecture session resources');
assert.match(studioPanel, /case 'ai_lecture_session':/, 'StudioPanel should render an icon for AI lecture sessions');
assert.match(studioPanel, /const openGeneratedFile = \(file: GeneratedFile\) => \{[\s\S]*file\.type === 'ai_lecture_session'/, 'StudioPanel should special-case AI lecture session files');
assert.match(studioPanel, /window\.localStorage\.setItem\('stitch-ai-lecture-session-id', file\.id\)/, 'StudioPanel should persist the selected session id before navigation');
assert.match(studioPanel, /window\.location\.hash = '#resources'/, 'StudioPanel should jump to course resources for AI lecture session playback');
assert.match(studioPanel, /onClick=\{\(\) => openGeneratedFile\(item\)\}/, 'StudioPanel artifact list should route clicks through openGeneratedFile');
assert.match(studioPanel, /openGeneratedFile\(f\)/, 'StudioPanel compact file list should route clicks through openGeneratedFile');

console.log('studioPanel.ai-lecture-session-entry tests passed');
