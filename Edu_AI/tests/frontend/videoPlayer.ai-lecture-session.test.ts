import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /useAiLecturerWebRtc/, 'VideoPlayer should use the native LiveTalking WebRTC hook');
assert.doesNotMatch(page, /getAiLecturerWebRtcUrl/, 'VideoPlayer should not iframe the LiveTalking demo page');
assert.doesNotMatch(page, /src=\{getAiLecturerWebRtcUrl\(\)\}/, 'VideoPlayer should never mount the LiveTalking demo page iframe');
assert.doesNotMatch(page, /<iframe[\s\S]*src=\{selectedPptPreviewUrl\}/s, 'Realtime lecture canvas should no longer render a PPT preview iframe');
assert.match(page, /<video ref=\{videoRef\} autoPlay playsInline muted className="h-full w-full bg-black object-contain"/, 'Realtime lecture canvas should focus on the digital human video feed');
assert.match(page, /createAiLectureSession/, 'VideoPlayer should create a persisted course AI lecture session');
assert.match(page, /startAiLectureSessionRecording/, 'VideoPlayer should start recording through the main backend');
assert.match(page, /stopAiLectureSessionRecording/, 'VideoPlayer should stop recording through the main backend');
assert.match(page, /patchAiLectureSessionSnapshot/, 'VideoPlayer should persist realtime speech and interruption events');
assert.match(page, /speakAiLecturerSentence\(\{\s*text:\s*sentence,\s*session_id:\s*activeLivetalkingSessionId\s*\}\)/, 'Speech calls should use the active LiveTalking session id');
assert.match(page, /askAiLecturer\(\{[\s\S]*session_id:\s*livetalkingSessionId/, 'Interrupt calls should use the real LiveTalking session id');
assert.match(page, /src=\{playbackUrl\(persistedRecordingUrl\)\}/, 'Saved course recordings should play through the course backend URL');

console.log('videoPlayer.ai-lecture-session tests passed');
