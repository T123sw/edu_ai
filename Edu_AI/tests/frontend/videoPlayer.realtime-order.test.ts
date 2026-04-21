import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');
const hook = readFileSync(new URL('../../src/stitch/hooks/useAiLecturerWebRtc.ts', import.meta.url), 'utf8');

const startRealtimeMatch = page.match(/async function startRealtimeSession[\s\S]*?\n  }\n\n  async function handleStartRealtimePlayback/);
assert.ok(startRealtimeMatch, 'VideoPlayer should define startRealtimeSession before the start button handler');

const startRealtimeSession = startRealtimeMatch[0];
const courseIndex = startRealtimeSession.indexOf('ensureAiLecturerCourse');
const scriptIndex = startRealtimeSession.indexOf('ensureSlideScript');
const webRtcIndex = startRealtimeSession.indexOf('startWebRtc');

assert.ok(courseIndex >= 0, 'startRealtimeSession should create/ensure the AI lecturer course');
assert.ok(scriptIndex >= 0, 'startRealtimeSession should generate the first slide script');
assert.ok(webRtcIndex >= 0, 'startRealtimeSession should connect LiveTalking WebRTC');
assert.ok(
  courseIndex < scriptIndex && scriptIndex < webRtcIndex,
  'Realtime startup should run create_course -> generate_script before waiting for LiveTalking /offer',
);

assert.match(hook, /AbortController/, 'LiveTalking WebRTC hook should abort stuck offer requests');
assert.match(hook, /AI_LECTURER_OFFER_TIMEOUT_MS/, 'LiveTalking WebRTC hook should expose a configurable offer timeout');
assert.match(hook, /window\.setTimeout\(\(\) => controller\.abort\(\), offerTimeoutMs\)/, 'LiveTalking offer should have a timeout guard');
assert.doesNotMatch(page, /function buildFallbackLectureSlides\(/, 'VideoPlayer should not silently fallback when create_course returns an empty outline');
assert.match(page, /function normalizeAiLecturerPages\(pages: unknown\)/, 'VideoPlayer should strictly validate create_course pages');
assert.match(page, /throw new Error\("AI Lecturer create_course returned empty pages\."/);
assert.match(page, /console\.info\(`\[AI Lecturer\]\[Realtime\] \$\{stage\}: start`\)/, 'Realtime startup should log each stage for diagnosis');
assert.match(page, /sync AI lecturer course snapshot/, 'Snapshot sync should have a named diagnostic stage before generate_script');

console.log('videoPlayer.realtime-order tests passed');
