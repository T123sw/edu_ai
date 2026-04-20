import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const types = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');
const videoApi = readFileSync(new URL('../../src/stitch/api/video.ts', import.meta.url), 'utf8');

assert.match(types, /export type AiLectureSessionMaterial/, 'AI lecture session material type should be exported');
assert.match(types, /export type AiLectureSessionDetail/, 'AI lecture session detail type should be exported');
assert.match(types, /export type AiLecturerOfferAnswer/, 'LiveTalking offer answer type should be exported');

assert.match(videoApi, /AI_LECTURER_LIVETALKING_URL/, 'Video API should expose the LiveTalking base URL');
assert.match(videoApi, /export function getAiLecturerOfferUrl/, 'Video API should expose the LiveTalking offer URL');
assert.match(videoApi, /export function createAiLectureSession/, 'Video API should create persisted AI lecture sessions');
assert.match(videoApi, /\/api\/courses\/\$\{courseId\}\/lecture-sessions/, 'Video API should call the course session endpoint');
assert.match(videoApi, /export function getAiLectureSession/, 'Video API should fetch persisted AI lecture sessions');
assert.match(videoApi, /export function patchAiLectureSessionSnapshot/, 'Video API should patch realtime session snapshots');
assert.match(videoApi, /export function startAiLectureSessionRecording/, 'Video API should start session recording through the main backend');
assert.match(videoApi, /export function stopAiLectureSessionRecording/, 'Video API should stop session recording through the main backend');

console.log('aiLecturerApi.session tests passed');
