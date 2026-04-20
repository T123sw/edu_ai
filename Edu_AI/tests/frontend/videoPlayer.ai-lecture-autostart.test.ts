import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /AI_LECTURE_AUTOSTART_REQUEST_KEY/, 'VideoPlayer should define an AI lecture autoplay handoff key');
assert.match(page, /readStoredJson<AiLectureAutoStartRequest>\(AI_LECTURE_AUTOSTART_REQUEST_KEY\)/, 'VideoPlayer should restore the autoplay request from localStorage');
assert.match(page, /readStoredString\(AI_LECTURE_PREFERRED_SESSION_KEY\)/, 'VideoPlayer should restore the preferred session id from localStorage');
assert.match(page, /if \(!autoStartRequest\?\.autoPlay \|\| materialsLoading \|\| autoStartAttemptedRef\.current\)/, 'VideoPlayer should guard the autoplay effect');
assert.match(page, /setMode\("online"\)/, 'VideoPlayer should switch to realtime mode for autoplay requests');
assert.match(page, /await startRealtimeSession\(\{\s*sessionId:\s*autoStartRequest\.sessionId \|\| null,\s*sourcePptMaterial,/s, 'VideoPlayer should automatically start the realtime session from the handoff payload');

console.log('videoPlayer.ai-lecture-autostart tests passed');
