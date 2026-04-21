import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');
const hook = readFileSync(new URL('../../src/stitch/hooks/useAiLecturerWebRtc.ts', import.meta.url), 'utf8');

const startRealtimeMatch = page.match(/async function startRealtimeSession[\s\S]*?\n  }\n\n  async function handleStartRealtimePlayback/);
assert.ok(startRealtimeMatch, 'VideoPlayer should define startRealtimeSession before the start button handler');

const startRealtimeSession = startRealtimeMatch[0];
const courseIndex = startRealtimeSession.indexOf('await ensureAiLecturerCourse');
const scriptIndex = startRealtimeSession.indexOf('await ensureSlideScript');
const webRtcIndex = startRealtimeSession.indexOf('await startWebRtc');

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

console.log('videoPlayer.realtime-order tests passed');

