import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const hook = readFileSync(new URL('../../src/stitch/hooks/useAiLecturerWebRtc.ts', import.meta.url), 'utf8');

assert.match(hook, /export function useAiLecturerWebRtc/, 'The AI lecturer WebRTC hook should be exported');
assert.match(hook, /new RTCPeerConnection\(/, 'The hook should create a native RTCPeerConnection');
assert.match(hook, /addTransceiver\("video",\s*\{\s*direction:\s*"recvonly"\s*\}\)/, 'The hook should receive remote video');
assert.match(hook, /addTransceiver\("audio",\s*\{\s*direction:\s*"recvonly"\s*\}\)/, 'The hook should receive remote audio');
assert.match(hook, /getAiLecturerOfferUrl\(\)/, 'The hook should post browser offers to the LiveTalking offer endpoint');
assert.match(hook, /setRemoteDescription/, 'The hook should apply the LiveTalking answer SDP');
assert.match(hook, /setLivetalkingSessionId\(answer\.sessionid\)/, 'The hook should expose the LiveTalking session id');
assert.match(hook, /videoRef/, 'The hook should expose a video ref for the remote stream');
assert.match(hook, /audioRef/, 'The hook should expose an audio ref for the remote stream');

console.log('aiLecturerWebRtcHook tests passed');
