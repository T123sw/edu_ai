import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(studioPanel, /createAiLectureSession\(/, 'StudioPanel should create a persisted AI lecture session before redirecting');
assert.match(studioPanel, /type:\s*'ai_lecture_session'/, 'StudioPanel should create an AI lecture session generated file');
assert.match(studioPanel, /createTeachingVideoTask\(courseId,\s*\{\s*ppt_material_id:\s*pptMaterialId\s*\}\)/, 'StudioPanel should also submit the offline teaching video task when launching realtime playback');
assert.match(studioPanel, /type:\s*'video'/, 'StudioPanel should create a pending offline video artifact for the workbench');
assert.match(studioPanel, /setTeachingVideoTaskId\(String\(offlineVideoResult\.value\.task_id \|\| ''\)\.trim\(\)\)/, 'StudioPanel should store the offline teaching video task id for polling');
assert.match(studioPanel, /setTeachingVideoPolling\(true\)/, 'StudioPanel should start polling the offline teaching video task immediately');
assert.match(studioPanel, /window\.localStorage\.setItem\(\s*AI_LECTURE_AUTOSTART_REQUEST_KEY/, 'StudioPanel should persist the autoplay handoff request');
assert.match(studioPanel, /autoPlay:\s*true/, 'StudioPanel should mark the handoff request for autoplay');
assert.match(studioPanel, /window\.location\.hash = '#video'/, 'StudioPanel should jump to the video player after submission');

console.log('studioPanel.ai-lecture-autostart tests passed');
