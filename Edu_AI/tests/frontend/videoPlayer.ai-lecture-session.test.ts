import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /useAiLecturerWebRtc/, 'VideoPlayer should use the native LiveTalking WebRTC hook');
assert.doesNotMatch(page, /getAiLecturerWebRtcUrl/, 'VideoPlayer should not iframe the LiveTalking demo page');
assert.doesNotMatch(page, /<iframe/, 'VideoPlayer should render native audio and video elements instead of an iframe');
assert.match(page, /createAiLectureSession/, 'VideoPlayer should create a persisted course AI lecture session');
assert.match(page, /startAiLectureSessionRecording/, 'VideoPlayer should start recording through the main backend');
assert.match(page, /stopAiLectureSessionRecording/, 'VideoPlayer should stop recording through the main backend');
assert.match(page, /patchAiLectureSessionSnapshot/, 'VideoPlayer should persist realtime speech and interruption events');
assert.match(page, /speakAiLecturerSentence\(\{\s*text:\s*sentence,\s*session_id:\s*livetalkingSessionId\s*\}\)/, 'Speech calls should use the real LiveTalking session id');
assert.match(page, /askAiLecturer\(\{[\s\S]*session_id:\s*livetalkingSessionId/, 'Interrupt calls should use the real LiveTalking session id');
assert.match(page, /src=\{playbackUrl\(persistedRecordingUrl\)\}/, 'Saved course recordings should play through the course backend URL');

console.log('videoPlayer.ai-lecture-session tests passed');
