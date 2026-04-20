import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /createAiLectureSession\(/, 'StudioPanel should create a persisted AI lecture session before redirecting');
assert.match(studioPanel, /type:\s*'ai_lecture_session'/, 'StudioPanel should create an AI lecture session generated file');
assert.match(studioPanel, /window\.localStorage\.setItem\(\s*AI_LECTURE_AUTOSTART_REQUEST_KEY/, 'StudioPanel should persist the autoplay handoff request');
assert.match(studioPanel, /autoPlay:\s*true/, 'StudioPanel should mark the handoff request for autoplay');
assert.match(studioPanel, /window\.location\.hash = '#video'/, 'StudioPanel should jump to the video player after submission');
assert.doesNotMatch(studioPanel, /createTeachingVideoTask\(courseId,\s*\{\s*ppt_material_id:/, 'StudioPanel should no longer launch the offline teaching video task for realtime playback');

console.log('studioPanel.ai-lecture-autostart tests passed');
