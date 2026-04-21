import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /AI_LECTURE_AUTOSTART_REQUEST_KEY/, 'VideoPlayer should define an AI lecture autoplay handoff key');
assert.match(page, /readStoredJson<AiLectureAutoStartRequest>\(AI_LECTURE_AUTOSTART_REQUEST_KEY\)/, 'VideoPlayer should restore the autoplay request from localStorage');
assert.match(page, /readStoredString\(AI_LECTURE_PREFERRED_SESSION_KEY\)/, 'VideoPlayer should restore the preferred session id from localStorage');
assert.match(page, /function clearStoredValue\(key: string\)/, 'VideoPlayer should clear autoplay handoff storage explicitly after handling it');
assert.match(page, /const \[autoStartReady, setAutoStartReady\] = useState\(false\);/, 'VideoPlayer should wait for a stable mount before consuming autoplay handoff state');
assert.match(page, /window\.setTimeout\(\(\) => \{\s*setAutoStartReady\(true\);\s*\}, 0\)/s, 'VideoPlayer should defer autoplay until the stable post-mount tick');
assert.match(page, /if \(!autoStartReady \|\| !autoStartRequest\?\.autoPlay \|\| materialsLoading \|\| autoStartAttemptedRef\.current\)/, 'VideoPlayer should guard the autoplay effect until the page is stably mounted');
assert.match(page, /clearStoredValue\(AI_LECTURE_AUTOSTART_REQUEST_KEY\);\s*setAutoStartRequest\(null\);/s, 'VideoPlayer should only clear the autoplay handoff request after it has been handled or dismissed');
assert.match(page, /setMode\("online"\)/, 'VideoPlayer should switch to realtime mode for autoplay requests');
assert.match(page, /await startRealtimeSession\(\{\s*sessionId:\s*autoStartRequest\.sessionId \|\| null,\s*sourcePptMaterial,/s, 'VideoPlayer should automatically start the realtime session from the handoff payload');

console.log('videoPlayer.ai-lecture-autostart tests passed');
