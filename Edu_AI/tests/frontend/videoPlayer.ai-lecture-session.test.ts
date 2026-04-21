import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../../src/stitch/pages/VideoPlayer.tsx', import.meta.url), 'utf8');

assert.match(page, /useAiLecturerWebRtc/, 'VideoPlayer should use the native LiveTalking WebRTC hook');
assert.doesNotMatch(page, /getAiLecturerWebRtcUrl/, 'VideoPlayer should not iframe the LiveTalking demo page');
assert.doesNotMatch(page, /src=\{getAiLecturerWebRtcUrl\(\)\}/, 'VideoPlayer should never mount the LiveTalking demo page iframe');
assert.match(page, /const realtimeStageSlideImageUrl = realtimeStageSlideImageUrls\[activeSlideIndex\] \|\| "";/, 'Realtime lecture canvas should resolve the current slide background from exported slide images');
assert.match(page, /fetchAuthenticatedBlobUrl\(realtimeStageSlideImageUrl\)/, 'Realtime lecture canvas should fetch the current slide image with API authentication');
assert.match(page, /<img[\s\S]*src=\{realtimeStageSlideObjectUrl\}/s, 'Realtime lecture canvas should render the authenticated slide image object URL as the stage background');
assert.match(page, /<video[\s\S]*ref=\{videoRef\}[\s\S]*className="absolute[\s\S]*z-20[\s\S]*object-contain/, 'Realtime lecture canvas should keep the digital human layered above the PPT background');
assert.match(page, /snapshot\.slide_image_urls/, 'Realtime lecture canvas should hydrate exported slide image urls from the AI lecture session snapshot');
assert.match(page, /createAiLectureSession/, 'VideoPlayer should create a persisted course AI lecture session');
assert.match(page, /startAiLectureSessionRecording/, 'VideoPlayer should start recording through the main backend');
assert.match(page, /stopAiLectureSessionRecording/, 'VideoPlayer should stop recording through the main backend');
assert.match(page, /patchAiLectureSessionSnapshot/, 'VideoPlayer should persist realtime speech and interruption events');
assert.match(page, /speakAiLecturerSentence\(\{\s*text:\s*sentence,\s*session_id:\s*activeLivetalkingSessionId\s*\}\)/, 'Speech calls should use the active LiveTalking session id');
assert.match(page, /askAiLecturer\(\{[\s\S]*session_id:\s*livetalkingSessionId/, 'Interrupt calls should use the real LiveTalking session id');
assert.match(page, /src=\{playbackUrl\(persistedRecordingUrl\)\}/, 'Saved course recordings should play through the course backend URL');

console.log('videoPlayer.ai-lecture-session tests passed');
